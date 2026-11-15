"""Cost impact simulator. Deterministic arithmetic only.

change per product unit = qty per unit x (new price - baseline)
period change           = change per unit x planned volume x share
negative = saving, positive = extra cost
"""
from __future__ import annotations

import pandas as pd

ASSUMPTIONS = [
    "Flat effect through BOM levels: the part's exploded quantity per product unit is used.",
    "Planned volumes are fixed at the values shown.",
    "Quantities per unit do not change.",
    "All other costs stay the same.",
    "Hypothetical: not a realized saving, and never added to historical spend.",
]


def simulate(rows: list[dict], baseline: float, new_price: float, share: float) -> dict:
    """rows: [{product_id, name, qty_per_unit, planned_volume (or None)}]. share in [0, 1]."""
    out = []
    total = 0.0
    has_vol = True
    for r in rows:
        q = float(r["qty_per_unit"])
        per_unit = q * (new_price - baseline)
        vol = r.get("planned_volume")
        if vol is None:
            has_vol = False
            period = None
        else:
            period = per_unit * float(vol) * share
            total += period
        out.append({**r, "cost_per_unit_now": q * baseline, "cost_per_unit_new": q * new_price, "change_per_unit": per_unit,
                    "period_change": period,
                    "formula": f"{q:g} x ({new_price:g} - {baseline:g}) x {vol if vol is not None else '?'} x {share*100:g}%"})
    return {"rows": out, "total_change": total if has_vol else None, "per_unit_only": not has_vol, "assumptions": ASSUMPTIONS}


def simulator_inputs(part_id: str, leaves: pd.DataFrame, products: pd.DataFrame, volumes: pd.DataFrame | None,
                     part_detail: dict) -> dict:
    act = products[products["status"] != "discontinued"]
    lv = leaves[(leaves["part_id"] == part_id) & leaves["product_id"].isin(act["product_id"])].merge(act, on="product_id")
    last_period = None
    planned = {}
    if volumes is not None and len(volumes):
        v = volumes.copy()
        v["product_id"] = v["product_id"].astype(str)
        if "period" in v:
            v["period"] = v["period"].astype(str)
            last_period = sorted(v["period"].unique())[-1]
            vv = v[v["period"] == last_period]
        else:
            vv = v
        planned = pd.to_numeric(vv["units_built"], errors="coerce").groupby(vv["product_id"]).sum().to_dict()
    rows = [{"product_id": r.product_id, "name": r.name, "qty_per_unit": float(r.qty_per_unit),
             "planned_volume": float(planned[r.product_id]) if r.product_id in planned else None} for r in lv.itertuples(index=False)]
    baselines = []
    if part_detail.get("wavg_price"):
        baselines.append({"key": "wavg", "label": "Weighted-average actual price", "value": part_detail["wavg_price"],
                          "source": "production spend / production quantity of linked lines"})
    for s in part_detail.get("suppliers", []):
        if s["kind"] == "production" and s["price"]:
            baselines.append({"key": f"supplier:{s['supplier']}", "label": f"{s['supplier']} price", "value": s["price"],
                              "source": f"{s['lines']} production line(s) from {s['supplier']}"})
    if part_detail.get("standard_cost") is not None:
        baselines.append({"key": "standard", "label": "Standard cost", "value": part_detail["standard_cost"], "source": "material master"})
    return {"part_id": part_id, "rows": rows, "baselines": baselines, "period": last_period, "assumptions": ASSUMPTIONS}
