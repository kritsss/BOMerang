from __future__ import annotations

import io
import json

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel

import service
from engine.learning import describe
from engine.ledger import CLASS_LABEL
from engine.simulator import simulate
from store.db import RuleVersion, select, session

from .common import clean, project_or_404, result_or_404

router = APIRouter()
HDR = Font(bold=True, color="FFFFFF")
HFILL = PatternFill("solid", fgColor="12151C")
FLAG = PatternFill("solid", fgColor="FFEDD5")


def _sheet(wb: Workbook, title: str, header: list[str], rows: list[list], note: str | None = None, flag_col: int | None = None):
    ws = wb.create_sheet(title[:31])
    r0 = 1
    if note:
        ws.cell(1, 1, note).font = Font(italic=True)
        r0 = 3
    for j, h in enumerate(header, 1):
        c = ws.cell(r0, j, h)
        c.font, c.fill = HDR, HFILL
    for i, row in enumerate(rows, r0 + 1):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, clean(v) if not isinstance(v, (dict, list)) else json.dumps(clean(v), ensure_ascii=False))
        if flag_col is not None and row[flag_col]:
            for j in range(1, len(header) + 1):
                ws.cell(i, j).fill = FLAG
    for j, h in enumerate(header, 1):
        ws.column_dimensions[get_column_letter(j)].width = min(60, max(10, len(h) + 4))
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    return ws


class ExportIn(BaseModel):
    scenario: dict | None = None


def _ev_text(ev: dict) -> str:
    parts = []
    for k in ("price", "balance", "coverage", "unit"):
        if ev.get(k) and ev[k].get("sentence"):
            parts.append(ev[k]["sentence"])
    if ev.get("timing"):
        parts.append("Timing fit: " + ", ".join(f"{p} {v*100:.0f}%" for p, v in ev["timing"]["fit"].items()))
    return " ".join(parts)


@router.post("/projects/{pid}/export")
def export(pid: int, body: ExportIn | None = None):
    proj = project_or_404(pid)
    res = result_or_404(pid)
    run = service.latest_run(pid)
    cur = res["display_currency"]
    wb = Workbook()
    wb.remove(wb.active)
    it = res["items"]
    pdesc = res["parts"].set_index("part_id")["description"].to_dict()
    decs = service.decisions(pid, active_only=False)
    overrides = {d["item_id"] for d in decs if d["override_refusal"] and not d["undone"]}
    _sheet(wb, "Links", ["Item", "Supplier", "Supplier part no", "Description", "Lines", f"Spend ({cur})", "Status", "Linked part",
                         "Part description", "Suggested part", "Step", "Confidence", "Reason", "Evidence", "Overrides a refusal"],
           [[r.item_id, r.supplier_name, r.supplier_pn, r.description, r.n_lines, r.spend_cents / 100, r.status_label, r.part_id,
             pdesc.get(r.part_id), r.suggestion_part_id, r.rung_label, round(r.confidence, 3), r.reason, _ev_text(r.evidence or {}),
             "YES" if r.item_id in overrides else ""] for r in it.sort_values("spend_cents", ascending=False).itertuples(index=False)],
           note=f"Rule version {run.rule_version} · run {run.id} · {run.finished_at} · display currency {cur}", flag_col=14)
    led = res["ledger"]
    prods = res["products"].set_index("product_id")["name"].to_dict()
    alloc = led[led["class"] == "allocated"].groupby(["product_id", "part_id"])["cents"].sum().reset_index()
    _sheet(wb, "Allocation by product", ["Product", "Name", "Part", "Part description", f"Allocated ({cur})"],
           [[r.product_id, prods.get(r.product_id), r.part_id, pdesc.get(r.part_id), r.cents / 100] for r in alloc.itertuples(index=False)],
           note="Allocated = required quantity x weighted-average production price, capped at what was bought.")
    s = res["summary"]
    rows = [[c["label"], c["group"], c["cents"] / 100] for c in s["classes"]]
    rows += [["Total of classes", "", s["ledger_cents"] / 100], ["Total spend cube", "", s["total_cents"] / 100],
             ["Difference to the spend cube", "", s["difference_cents"] / 100]]
    _sheet(wb, "Spend explainer", ["Class", "Group", f"Amount ({cur})"], rows,
           note=f"{s['explained_share']*100:.1f}% of spend is explained by products (allocated).")
    L = res["lines"].set_index("line_id")
    _sheet(wb, "Explainer lines", ["Line", "Class", "Product", "Part", f"Counted ({cur})", "Supplier", "Description", "Qty", "Unit", "Currency", "Original amount"],
           [[r.line_id, CLASS_LABEL.get(r._2, r._2), r.product_id, r.part_id, r.cents / 100, L.at[r.line_id, "supplier_name"], L.at[r.line_id, "description"],
             L.at[r.line_id, "qty"], L.at[r.line_id, "purchase_uom"], L.at[r.line_id, "currency"], L.at[r.line_id, "amount"]]
            for r in led.itertuples(index=False)])
    brows = []
    for b in res["bom_cost"]:
        for r in b["rows"]:
            brows.append([b["product_id"], b["name"], r["level"], ("  " * (r["level"] - 1)) + r["part_id"], r["description"], r["qty_per_parent"],
                          r["ext_qty"], r["standard_cost"], r["std_ext"], r["actual_price"], r["actual_ext"],
                          (r["allocated_cents"] or 0) / 100 if r["is_leaf"] else None, r["link"]])
        brows.append([b["product_id"], b["name"], "", "TOTAL per unit", "", "", "", "", b["std_cost_per_unit"], "", b["actual_cost_per_unit"],
                      b["allocated_cents"] / 100, f"coverage {b['coverage']*100:.0f}%"])
    _sheet(wb, "BOM cost", ["Product", "Name", "Level", "Part", "Description", "Qty per parent", "Qty per product", "Standard cost", "Std cost x qty",
                            "Actual price", "Actual x qty", f"Allocated spend ({cur})", "Link"], brows)
    sc = (body.scenario if body else None) or None
    if sc and sc.get("rows"):
        r = simulate(sc["rows"], float(sc["baseline"]), float(sc["new_price"]), float(sc.get("share", 1.0)))
        srows = [[x["product_id"], x.get("name"), x["qty_per_unit"], sc["baseline"], sc["new_price"], x["change_per_unit"],
                  x.get("planned_volume"), sc.get("share", 1.0), x["period_change"], x["formula"]] for x in r["rows"]]
        srows.append(["TOTAL", "", "", "", "", "", "", "", r["total_change"], "negative = saving, positive = extra cost"])
        ws = _sheet(wb, "Scenario", ["Product", "Name", "Qty per unit", "Baseline price", "New price", "Change per unit", "Planned units", "Share",
                                     "Period change", "Formula"], srows,
                    note=f"Part {sc.get('part_id')} · baseline: {sc.get('baseline_label', '')} · hypothetical, not realized. " + " ".join(r["assumptions"]))
    else:
        _sheet(wb, "Scenario", ["Note"], [["No scenario exported. Use 'Export scenario' on the Simulate screen."]])
    _sheet(wb, "Review decisions", ["When", "Who", "Action", "Item", "Supplier", "Description", "Part", "Unit factor", "Reason", "Overrides a refusal", "Undone"],
           [[d["created_at"], d["who"], d["action"], d["item_id"], d["supplier"], d["description"], d["part_id"], d["unit_factor"], d["reason"],
             "YES" if d["override_refusal"] else "", "yes" if d["undone"] else ""] for d in decs], flag_col=9)
    lr = service.learned_rules(pid, active_only=False)
    _sheet(wb, "Learned rules", ["Id", "Kind", "Rule", "Who", "When", "Why", "Active"],
           [[r["id"], r["kind"], describe(r), r["who"], r["created_at"], r["why"], "yes" if r["active"] else "removed"] for r in lr])
    v, rules = service.get_rules(pid)
    with session() as ss:
        vers = ss.exec(select(RuleVersion).where(RuleVersion.project_id == pid).order_by(RuleVersion.version)).all()
    rrows = [["Current version", v, "", ""], ["Run used version", run.rule_version, "", ""]]
    rrows += [[f"v{x.version}", x.who, x.why, "; ".join(x.loosened or [])] for x in vers]
    rrows += [["hard_attributes", json.dumps(rules.get("hard_attributes")), "", ""], ["price_band", json.dumps(rules.get("price_band")), "", ""],
              ["thresholds", json.dumps(rules.get("thresholds")), "", ""], ["synonyms (count)", len(rules.get("synonyms", [])), "", ""]]
    _sheet(wb, "Rule version", ["Key", "Value", "Why", "Loosened (flag)"], rrows, flag_col=3)
    rd = service.project_readiness(pid)
    _sheet(wb, "Data readiness", ["Feature", "On", "Why", "How to turn it on"],
           [[f["label"], "on" if f["on"] else "off", f["why"], f["how"]] for f in rd["features"]] +
           [["Unknown purchase units", "", ", ".join(rd["unknown_units"]), ""], ["Files", "", "; ".join(f"{f['filename']} {f['sheet']} → {f['file_type']}" for f in rd["files"] if f["status"] == "mapped"), ""]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    name = f"BOMerang_{proj.name.replace(' ', '_')}_run{run.id}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/projects/{pid}/export/links.csv")
def links_csv(pid: int):
    res = result_or_404(pid)
    it = res["items"].copy()
    it["spend"] = it["spend_cents"] / 100
    it["evidence_summary"] = it["evidence"].map(lambda e: _ev_text(e or {}))
    cols = ["item_id", "supplier_name", "supplier_pn", "description", "n_lines", "spend", "status_label", "part_id", "suggestion_part_id",
            "rung_label", "confidence", "reason", "evidence_summary"]
    buf = io.StringIO()
    it[cols].to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="links.csv"'})
