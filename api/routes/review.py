from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import service
from engine.checks import base_qty
from engine.learning import describe, rules_from_decision
from engine.normalize import canon_unit
from store.db import Decision, LearnedRule, select, session

from .common import clean, records, result_or_404

router = APIRouter()


@router.get("/projects/{pid}/review")
def review_queue(pid: int):
    res = result_or_404(pid)
    it = res["items"]
    q = it[it["status"] == "review"].sort_values(["money_at_stake_cents", "spend_cents"], ascending=False)
    total = int(q["money_at_stake_cents"].sum())
    cum, k80, acc = [], None, 0
    for i, v in enumerate(q["money_at_stake_cents"], start=1):
        acc += int(v)
        share = acc / total if total else 1.0
        cum.append(share)
        if k80 is None and share >= 0.8:
            k80 = i
    pdesc = res["parts"].set_index("part_id")["description"].to_dict()
    queue = records(q, ["item_id", "supplier_name", "supplier_pn", "description", "spend_cents", "money_at_stake_cents", "suggestion_part_id",
                        "reason", "confidence", "rung_label", "ai_proposed"])
    for r in queue:
        r["suggestion_description"] = pdesc.get(r["suggestion_part_id"])
    ref = it[it["status"] == "refused"].sort_values("spend_cents", ascending=False)
    refused = records(ref, ["item_id", "supplier_name", "description", "spend_cents", "suggestion_part_id", "reason"])
    decided = service.decisions(pid)
    return {"queue": queue, "cumulative": cum, "k80": k80, "stake_total_cents": total, "refused": refused,
            "decided_count": len(decided), "currency": res["display_currency"]}


@router.get("/projects/{pid}/items/{item_id}")
def item_detail(pid: int, item_id: str):
    res = result_or_404(pid)
    it = res["items"]
    row = it[it["item_id"] == item_id]
    if row.empty:
        raise HTTPException(404, "Item not found")
    r = clean(row.iloc[0].to_dict())
    parts = res["parts"].set_index("part_id")
    leaves = res["leaves"]
    prods = res["products"].set_index("product_id")["name"].to_dict()
    req = res["req_pp"]
    alloc = res["part_alloc"].set_index("part_id").to_dict("index") if len(res["part_alloc"]) else {}

    def part_card(p):
        if p is None or p not in parts.index:
            return None
        used = leaves[leaves["part_id"] == p]
        rq = req[req["part_id"] == p] if len(req) else req
        a = alloc.get(p, {})
        return clean({"part_id": p, "description": parts.at[p, "description"], "category": parts.at[p, "category"],
                      "base_uom": parts.at[p, "base_uom"], "standard_cost": parts.at[p, "standard_cost"], "attrs": parts.at[p, "attrs"],
                      "used_in": [{"product_id": u.product_id, "name": prods.get(u.product_id, u.product_id), "qty_per_unit": u.qty_per_unit}
                                  for u in used.itertuples(index=False)],
                      "required": float(rq["required"].sum()) if len(rq) else None, "wavg_price": a.get("wavg_price")})
    ev = r.get("evidence") or {}
    cand_ids = [c["part_id"] for c in ev.get("candidates", [])]
    main = r.get("part_id") or r.get("suggestion_part_id")
    L = res["lines"]
    lines = records(L[L["item_id"] == item_id].sort_values("cents", ascending=False).head(200),
                    ["line_id", "description", "qty", "purchase_uom", "unit_price", "currency", "cents", "month", "cost_center", "is_service", "class"])
    all_parts = [{"part_id": p, "description": d} for p, d in zip(res["parts"]["part_id"], res["parts"]["description"])]
    return {"item": r, "main_part": part_card(main), "candidates": [part_card(p) for p in cand_ids],
            "lines": lines, "currency": res["display_currency"], "part_options": all_parts[:2000],
            "unit_unknown": "unit" in ev or ("nknown" in (r.get("reason") or "") and "unit" in (r.get("reason") or "").lower())}


@router.post("/projects/{pid}/review/undo")
def undo(pid: int):
    result_or_404(pid)
    with session() as s:
        d = s.exec(select(Decision).where(Decision.project_id == pid, Decision.undone == False).order_by(Decision.id.desc())).first()  # noqa: E712
        if d is None:
            raise HTTPException(400, "Nothing to undo")
        d.undone = True
        s.add(d)
        for lr in s.exec(select(LearnedRule).where(LearnedRule.decision_id == d.id)).all():
            lr.active = False
            s.add(lr)
        s.commit()
    service.light_run(pid)
    return {"ok": True, "undone_item_id": d.item_id, "summary": service.make_summary(service.result(pid))}


class DecisionIn(BaseModel):
    action: str                      # approve | reject
    part_id: str | None = None
    unit_factor: float | None = None
    reason: str = ""
    who: str = "analyst"
    override_reason: str | None = None


@router.post("/projects/{pid}/review/{item_id}")
def decide(pid: int, item_id: str, body: DecisionIn):
    res = result_or_404(pid)
    it = res["items"]
    row = it[it["item_id"] == item_id]
    if row.empty:
        raise HTTPException(404, "Item not found")
    r = row.iloc[0]
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")
    part = body.part_id or r["suggestion_part_id"] or r["part_id"]
    override = False
    base_uom = None
    if body.action == "approve":
        if not part or part not in set(res["parts"]["part_id"]):
            raise HTTPException(400, "Choose a part to link to.")
        ev = r["evidence"] or {}
        refused_for = {c["part_id"] for c in ev.get("refused", [])}
        if part in refused_for:
            if not (body.override_reason and body.override_reason.strip()):
                raise HTTPException(400, "This part was refused on a hard attribute. A written reason is required to override.")
            override = True
        base_uom = res["parts"].set_index("part_id").at[part, "base_uom"]
        items_s1 = res["lines"][res["lines"]["item_id"] == item_id]
        q = items_s1[~items_s1["is_service"]].groupby(items_s1["purchase_uom_c"].fillna(""))["qty"].sum().to_dict()
        conv = []
        if body.unit_factor:
            conv = [{"purchase_uom": u, "base_uom": base_uom, "factor": body.unit_factor} for u in q]
        inp = service.build_inputs(pid)
        glob = list(inp.rules.get("unit_conversions") or []) + (inp.conversions.to_dict("records") if inp.conversions is not None else [])
        glob += [l["value"] for l in inp.learned if l["kind"] == "unit" and (not l["value"].get("item_key") or l["value"]["item_key"] == r["item_key"])]
        qty, unknown = base_qty(q, base_uom, conv + glob)
        if qty is None and q:
            raise HTTPException(400, f"Unit unknown ({', '.join(unknown)}). Enter how many {base_uom} one purchase unit holds.")
    with session() as s:
        d = Decision(project_id=pid, item_id=item_id, item_key=r["item_key"], action=body.action, part_id=part if body.action == "approve" else None,
                     unit_factor=body.unit_factor, purchase_uom=canon_unit(r["purchase_uom"]) if r["purchase_uom"] else None, base_uom=base_uom,
                     reason=(body.override_reason or body.reason or "").strip(), who=body.who or "analyst", override_refusal=override,
                     spend_cents=int(r["spend_cents"]), description=str(r["description"]), supplier=str(r["supplier_name"]))
        s.add(d)
        s.commit()
        s.refresh(d)
        made = []
        item = {"supplier_key": r["supplier_key"], "supplier_pn": r["supplier_pn"], "item_key": r["item_key"],
                "purchase_uom": canon_unit(r["purchase_uom"]) if r["purchase_uom"] else None, "supplier_name": r["supplier_name"],
                "description": r["description"]}
        for lr in rules_from_decision(item, {"action": body.action, "part_id": part, "unit_factor": body.unit_factor, "base_uom": base_uom}):
            row_ = LearnedRule(project_id=pid, kind=lr["kind"], value=lr["value"], who=d.who, why=d.reason or ("approved in review" if body.action == "approve" else "rejected in review"), decision_id=d.id)
            s.add(row_)
            made.append(describe(lr))
        s.commit()
    rid = service.light_run(pid)
    summ = service.make_summary(service.result(pid))
    return {"ok": True, "decision_id": d.id, "saved_rules": made, "run_id": rid, "summary": summ}


@router.get("/projects/{pid}/decisions")
def list_decisions(pid: int):
    return service.decisions(pid, active_only=False)
