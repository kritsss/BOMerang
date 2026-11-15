from __future__ import annotations

from fastapi import APIRouter, HTTPException

from engine.costing import part_detail

from .common import clean, result_or_404

router = APIRouter()


@router.get("/projects/{pid}/parts")
def list_parts(pid: int):
    res = result_or_404(pid)
    it = res["items"]
    linked = it[it["status"].isin(["auto", "evidence", "human"])].groupby("part_id")["spend_cents"].sum().to_dict()
    used = res["leaves"].groupby("part_id")["product_id"].nunique().to_dict()
    out = []
    for r in res["parts"].itertuples(index=False):
        out.append({"part_id": r.part_id, "description": r.description, "category": r.category, "spend_cents": int(linked.get(r.part_id, 0)),
                    "used_in": int(used.get(r.part_id, 0))})
    out.sort(key=lambda x: -x["spend_cents"])
    return clean(out)


@router.get("/projects/{pid}/parts/{part_id}")
def get_part(pid: int, part_id: str):
    res = result_or_404(pid)
    d = part_detail(part_id, res["parts"], res["items"], res["lines"], res["ledger"], res["leaves"], res["products"], res["req_pp"], res["part_alloc"])
    if not d:
        raise HTTPException(404, "Part not found")
    d["currency"] = res["display_currency"]
    return clean(d)
