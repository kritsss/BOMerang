from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.costing import part_detail
from engine.simulator import simulate, simulator_inputs

from .common import clean, result_or_404

router = APIRouter()


@router.get("/projects/{pid}/simulate/{part_id}")
def sim_inputs(pid: int, part_id: str):
    res = result_or_404(pid)
    d = part_detail(part_id, res["parts"], res["items"], res["lines"], res["ledger"], res["leaves"], res["products"], res["req_pp"], res["part_alloc"])
    if not d:
        raise HTTPException(404, "Part not found")
    out = simulator_inputs(part_id, res["leaves"], res["products"], res.get("volumes"), d)
    out.update(description=d["description"], base_uom=d["base_uom"], currency=res["display_currency"])
    return clean(out)


class SimIn(BaseModel):
    rows: list[dict]
    baseline: float
    new_price: float
    share: float = 1.0


@router.post("/projects/{pid}/simulate")
def sim(pid: int, body: SimIn):
    return clean(simulate(body.rows, body.baseline, body.new_price, body.share))
