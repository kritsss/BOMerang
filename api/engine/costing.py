"""BOM cost per product and the part explorer. Deterministic."""
from __future__ import annotations

import numpy as np
import pandas as pd

LINKED = ("auto", "evidence", "human")


def _f(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and np.isnan(x):
            return None
    except TypeError:
        pass
    return float(x)


def bom_cost(tree: pd.DataFrame, products: pd.DataFrame, parts: pd.DataFrame, part_alloc: pd.DataFrame,
             ledger: pd.DataFrame, items: pd.DataFrame) -> list[dict]:
    pinfo = parts.set_index("part_id") if len(parts) else pd.DataFrame()
    wavg = part_alloc.set_index("part_id")["wavg_price"].to_dict() if len(part_alloc) else {}
    alloc = ledger[ledger["class"] == "allocated"].groupby(["product_id", "part_id"])["cents"].sum().to_dict() if len(ledger) else {}
    link_state = {}
    for st, p, s in zip(items["status"], items["part_id"], items["suggestion_part_id"]):
        if st in LINKED and p:
            link_state[p] = "linked"
        elif st == "review" and s and link_state.get(s) != "linked":
            link_state[s] = "pending"
    out = []
    for prod in products.itertuples(index=False):
        t = tree[tree["product_id"] == prod.product_id]
        rows = []
        for r in t.itertuples(index=False):
            p = r.component_id
            desc = pinfo.at[p, "description"] if p in pinfo.index else (r.description_as_written or "")
            std = _f(pinfo.at[p, "standard_cost"]) if p in pinfo.index else None
            w = _f(wavg.get(p))
            rows.append({"level": int(r.level), "parent_id": r.parent_id, "part_id": p, "description": str(desc or ""),
                         "qty_per_parent": float(r.qty_per_parent), "ext_qty": float(r.ext_qty), "is_leaf": bool(r.is_leaf),
                         "standard_cost": std, "std_ext": std * r.ext_qty if std is not None and r.is_leaf else None,
                         "actual_price": w, "actual_ext": w * r.ext_qty if w is not None and r.is_leaf else None,
                         "allocated_cents": int(alloc.get((prod.product_id, p), 0)) if r.is_leaf else None,
                         "link": link_state.get(p, "none") if r.is_leaf else None})
        leaves = [r for r in rows if r["is_leaf"]]
        cov = (sum(1 for r in leaves if r["link"] == "linked") / len(leaves)) if leaves else 0.0
        out.append({"product_id": prod.product_id, "name": prod.name, "status": prod.status, "rows": rows,
                    "std_cost_per_unit": sum(r["std_ext"] or 0 for r in leaves),
                    "actual_cost_per_unit": sum(r["actual_ext"] or 0 for r in leaves),
                    "actual_known_lines": sum(1 for r in leaves if r["actual_ext"] is not None),
                    "leaf_lines": len(leaves), "coverage": cov,
                    "allocated_cents": int(sum(r["allocated_cents"] or 0 for r in leaves))})
    return out


def part_detail(part_id: str, parts: pd.DataFrame, items: pd.DataFrame, lines: pd.DataFrame, ledger: pd.DataFrame,
                leaves: pd.DataFrame, products: pd.DataFrame, req_pp: pd.DataFrame, part_alloc: pd.DataFrame) -> dict:
    pinfo = parts.set_index("part_id")
    if part_id not in pinfo.index:
        return {}
    pr = pinfo.loc[part_id]
    linked_items = items[(items["part_id"] == part_id) & items["status"].isin(LINKED)]
    L = lines[lines["item_id"].isin(linked_items["item_id"])]
    spend_cents = int(L["cents"].sum())
    # price per base unit by supplier, production vs service
    suppliers = []
    for (sk, svc), g in L.groupby(["supplier_name", "is_service"]):
        q = g["base_qty"].sum()
        c = int(g["cents"].sum())
        suppliers.append({"supplier": sk, "kind": "service" if svc else "production", "cents": c, "qty": float(q) if q else 0.0,
                          "price": (c / 100.0) / q if q else None, "lines": int(len(g))})
    prod_prices = [s["price"] for s in suppliers if s["kind"] == "production" and s["price"]]
    gap = (max(prod_prices) - min(prod_prices)) if len(prod_prices) >= 2 else 0.0
    gap_pct = gap / min(prod_prices) if len(prod_prices) >= 2 and min(prod_prices) > 0 else 0.0
    used = leaves[leaves["part_id"] == part_id].merge(products, on="product_id", how="left")
    req = req_pp[req_pp["part_id"] == part_id].set_index("product_id") if len(req_pp) else pd.DataFrame()
    alloc = ledger[(ledger["class"] == "allocated") & (ledger["part_id"] == part_id)].groupby("product_id")["cents"].sum().to_dict()
    prods = []
    for r in used.itertuples(index=False):
        prods.append({"product_id": r.product_id, "name": getattr(r, "name", r.product_id) or r.product_id, "status": getattr(r, "status", "active"),
                      "qty_per_unit": float(r.qty_per_unit),
                      "units_built": float(req.at[r.product_id, "units_built"]) if r.product_id in req.index else None,
                      "allocated_cents": int(alloc.get(r.product_id, 0))})
    refused = items[(items["status"] == "refused") & (items["suggestion_part_id"] == part_id)]
    refused_list = [{"item_id": r.item_id, "supplier": r.supplier_name, "description": r.description, "reason": r.reason,
                     "spend_cents": int(r.spend_cents), "price_per_base": None} for r in refused.itertuples(index=False)]
    # also items refused for this part while linked/refused elsewhere
    for r in items.itertuples(index=False):
        if r.item_id in set(refused["item_id"]):
            continue
        ev = r.evidence or {}
        for c in ev.get("refused", []):
            if c["part_id"] == part_id and r.part_id != part_id and c.get("type_ok", True):
                diff = [a for a in c["attrs"] if a["hard"] and a["result"] == "differ"]
                refused_list.append({"item_id": r.item_id, "supplier": r.supplier_name, "description": r.description,
                                     "reason": f"{diff[0]['attr']} differs: {diff[0]['why']}" if diff else "hard attribute differs",
                                     "spend_cents": int(r.spend_cents), "price_per_base": None})
                break
    pa = part_alloc.set_index("part_id").to_dict("index").get(part_id, {}) if len(part_alloc) else {}
    month = []
    if L["month"].notna().any():
        lp = L[~L["is_service"] & L["base_qty"].notna()]
        for (m, s), g in lp.groupby(["month", "supplier_name"]):
            q = g["base_qty"].sum()
            if q:
                month.append({"month": m, "supplier": s, "price": (g["cents"].sum() / 100.0) / q})
    return {"part_id": part_id, "description": pr["description"], "category": pr["category"], "base_uom": pr["base_uom"],
            "standard_cost": _f(pr["standard_cost"]), "attrs": pr["attrs"], "spend_cents": spend_cents,
            "used_in": len({p["product_id"] for p in prods}), "price_gap": gap, "price_gap_pct": gap_pct,
            "refused_count": len(refused_list), "suppliers": suppliers, "products": prods, "refused": refused_list,
            "wavg_price": _f(pa.get("wavg_price")), "required": _f(pa.get("required")),
            "linked_items": [{"item_id": r.item_id, "supplier": r.supplier_name, "description": r.description, "status": r.status_label,
                              "spend_cents": int(r.spend_cents)} for r in linked_items.itertuples(index=False)],
            "price_by_month": month}
