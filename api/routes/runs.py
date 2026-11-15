from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

import service
from engine.ledger import CLASS_GROUP, CLASS_LABEL
from store.db import Run, session, select

from .common import clean, project_or_404, records, result_or_404

router = APIRouter()


def _run_out(r: Run):
    return {"id": r.id, "kind": r.kind, "status": r.status, "progress": r.progress, "message": r.message, "error": r.error,
            "rule_version": r.rule_version, "created_at": r.created_at, "finished_at": r.finished_at, "summary": r.summary}


@router.post("/projects/{pid}/runs")
def start_run(pid: int):
    project_or_404(pid)
    rd = service.project_readiness(pid)
    if not rd["can_run"]:
        raise HTTPException(400, " ".join(rd["blocking"]))
    rid = service.start_full_run(pid)
    with session() as s:
        return _run_out(s.get(Run, rid))


@router.get("/projects/{pid}/runs")
def list_runs(pid: int):
    project_or_404(pid)
    with session() as s:
        rows = s.exec(select(Run).where(Run.project_id == pid).order_by(Run.id.desc())).all()
    return [_run_out(r) for r in rows[:50]]


@router.get("/projects/{pid}/runs/{rid}")
def get_run(pid: int, rid: int):
    with session() as s:
        r = s.get(Run, rid)
    if r is None or r.project_id != pid:
        raise HTTPException(404, "Run not found")
    return _run_out(r)


@router.get("/projects/{pid}/summary")
def summary(pid: int):
    project_or_404(pid)
    last = service.latest_run(pid)
    if last is None:
        return {"has_run": False}
    return {"has_run": True, "run": _run_out(last)}


LINK_COLS = ["item_id", "supplier_name", "supplier_pn", "description", "n_lines", "spend_cents", "status", "status_label", "part_id",
             "suggestion_part_id", "rung_label", "reason", "confidence", "money_at_stake_cents", "price_per_base", "base_qty", "purchase_uom"]


@router.get("/projects/{pid}/links")
def links(pid: int, status: str | None = None):
    res = result_or_404(pid)
    it = res["items"]
    if status:
        it = it[it["status"].isin(status.split(","))]
    it = it.sort_values("spend_cents", ascending=False)
    pdesc = res["parts"].set_index("part_id")["description"].to_dict()
    out = records(it, LINK_COLS)
    for r in out:
        p = r.get("part_id") or r.get("suggestion_part_id")
        r["part_description"] = pdesc.get(p) if p else None
    return out


@router.get("/projects/{pid}/search")
def search(pid: int, q: str = ""):
    res = service.result(pid)
    if res is None:
        return {"parts": [], "suppliers": [], "products": []}
    ql = q.lower().strip()
    parts = res["parts"]
    linked = set(res["items"].loc[res["items"]["status"].isin(["auto", "evidence", "human"]), "part_id"].dropna())
    pm = parts[parts["part_id"].str.lower().str.contains(ql, regex=False) | parts["description"].str.lower().str.contains(ql, regex=False)] if ql else parts
    pm = pm.assign(_l=pm["part_id"].isin(linked)).sort_values(["_l", "part_id"], ascending=[False, True]).head(30)
    sup = res["items"].groupby("supplier_name")["spend_cents"].sum().reset_index()
    if ql:
        sup = sup[sup["supplier_name"].str.lower().str.contains(ql, regex=False)]
    prods = res["products"]
    if ql:
        prods = prods[prods["product_id"].str.lower().str.contains(ql, regex=False) | prods["name"].str.lower().str.contains(ql, regex=False)]
    return {"parts": [{"part_id": r.part_id, "description": r.description, "linked": bool(r._l)} for r in pm.itertuples(index=False)],
            "suppliers": records(sup.sort_values("spend_cents", ascending=False).head(15)),
            "products": records(prods.head(15), ["product_id", "name", "status"])}


LINE_COLS = ["line_id", "supplier_name", "supplier_pn", "description", "qty", "purchase_uom", "unit_price", "currency", "amount",
             "fx_rate", "month", "cost_center", "status", "part_id", "class", "base_qty"]


@router.get("/projects/{pid}/receipts")
def receipts(pid: int, kind: str, key: str = "", product: str | None = None, supplier: str | None = None, limit: int = 500):
    """The lines behind any number, plus its formula."""
    res = result_or_404(pid)
    L = res["lines"]
    led = res["ledger"]
    cur = res["display_currency"]
    formula, title = "", ""
    if kind == "class":
        sel = led[led["class"] == key]
        if product:
            sel = sel[sel["product_id"] == product]
        share = sel.groupby("line_id")["cents"].sum()
        lines = L[L["line_id"].isin(share.index)].copy()
        lines["counted_cents"] = lines["line_id"].map(share)
        title = CLASS_LABEL.get(key, key) + (f" · {product}" if product else "")
        formula = _class_formula(key, cur)
    elif kind == "total":
        lines = L.copy()
        lines["counted_cents"] = lines["cents"]
        title = "All spend"
        formula = f"Sum of every spend line, converted to {cur} with the FX rates. Each line is counted once."
    elif kind == "part":
        it = res["items"]
        ids = it.loc[(it["part_id"] == key) & it["status"].isin(["auto", "evidence", "human"]), "item_id"]
        lines = L[L["item_id"].isin(ids)].copy()
        if supplier:
            lines = lines[lines["supplier_name"] == supplier]
        lines["counted_cents"] = lines["cents"]
        title = f"Lines linked to {key}" + (f" from {supplier}" if supplier else "")
        formula = "Price per piece = line spend / quantity in the part's base unit. Weighted-average price = production spend / production quantity (service lines excluded)."
    elif kind == "item":
        lines = L[L["item_id"] == key].copy()
        lines["counted_cents"] = lines["cents"]
        title = "Lines of this supplier item"
        formula = "A supplier item pools all lines with the same supplier and supplier part number (or description)."
    elif kind == "group":
        classes = [k for k, g in CLASS_GROUP.items() if g == key]
        share = led[led["class"].isin(classes)].groupby("line_id")["cents"].sum()
        lines = L[L["line_id"].isin(share.index)].copy()
        lines["counted_cents"] = lines["line_id"].map(share)
        title = {"explained": "Explained", "waiting": "Waiting for a person", "not_explained": "Not explained"}.get(key, key)
        formula = "Sum of the classes in this group."
    else:
        raise HTTPException(400, "Unknown receipt kind")
    lines = lines.sort_values("counted_cents", ascending=False)
    reason = res["items"].set_index("item_id")["reason"]
    out = records(lines.head(limit), LINE_COLS + ["counted_cents", "item_id"])
    for r in out:
        r["reason"] = reason.get(r["item_id"])
    return {"title": title, "formula": formula, "count": int(len(lines)), "total_cents": int(lines["counted_cents"].sum()),
            "lines": out, "truncated": len(lines) > limit, "currency": cur}


def _class_formula(k: str, cur: str) -> str:
    return {
        "allocated": "For each part: required quantity (exploded BOM qty x units built) x weighted-average production price, capped at what was bought. Split across products by required quantity.",
        "beyond_need": "Production spend on linked parts minus the amount allocated to products.",
        "service": "Lines whose cost center or description says spare, service or warranty (Rules → service keywords). Shown, never split across products.",
        "shop_supplies": "Lines on maintenance/MRO cost centers, shop-supply keywords, or linked to a shop-supply category (Rules).",
        "pending_review": "Lines of supplier items waiting for your review.",
        "refused": "Lines that look like a BOM part but differ on a hard attribute. Never linked automatically.",
        "not_in_bom": "Lines linked to a part that is in the master but in no active product's BOM.",
        "no_match": "Lines with no plausible part, or marked 'not a BOM part' by a person.",
        "linked_unallocated": "Lines linked to BOM parts. Upload production volumes to allocate them to products.",
    }.get(k, "")


@router.get("/projects/{pid}/moneyflow")
def moneyflow(pid: int):
    res = result_or_404(pid)
    s = res["summary"]
    led = res["ledger"]
    prods = res["products"].set_index("product_id")["name"].to_dict()
    by_prod = led[led["class"] == "allocated"].groupby("product_id")["cents"].sum().sort_values(ascending=False)
    unexplained = led[led["class"].isin(["refused", "not_in_bom", "no_match", "pending_review"])]
    top_un = unexplained.groupby(["class", "item_id"])["cents"].sum().reset_index().sort_values("cents", ascending=False).head(12)
    it = res["items"].set_index("item_id")
    top = [{"class": r["class"], "label": CLASS_LABEL[r["class"]], "item_id": r["item_id"], "cents": int(r["cents"]),
            "description": it.at[r["item_id"], "description"], "supplier": it.at[r["item_id"], "supplier_name"],
            "reason": it.at[r["item_id"], "reason"]} for _, r in top_un.iterrows()]
    return clean({"summary": s, "has_volumes": res["has_volumes"], "currency": res["display_currency"],
                  "products": [{"product_id": p, "name": prods.get(p, p), "cents": int(c)} for p, c in by_prod.items()],
                  "unexplained_top": top, "bom_cost": res["bom_cost"]})
