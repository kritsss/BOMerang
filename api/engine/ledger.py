"""Allocation and the 8-class spend explainer. All money in integer cents so totals reconcile exactly."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

CLASSES = [
    ("allocated", "Allocated to products", "explained"),
    ("beyond_need", "Bought beyond need", "explained"),
    ("service", "Service and warranty", "explained"),
    ("shop_supplies", "Shop supplies (not production)", "explained"),
    ("pending_review", "Pending review", "waiting"),
    ("refused", "Refused look-alike", "not_explained"),
    ("not_in_bom", "Not in any current BOM", "not_explained"),
    ("no_match", "No match found", "not_explained"),
]
# used only when no production volumes are loaded (allocation is off)
UNALLOCATED = ("linked_unallocated", "Linked to a BOM part (no volumes to allocate)", "explained")
CLASS_LABEL = {k: l for k, l, _ in CLASSES + [UNALLOCATED]}
CLASS_GROUP = {k: g for k, _, g in CLASSES + [UNALLOCATED]}


def split_int(total: int, weights: list[float]) -> list[int]:
    """Split an integer total into integers proportional to weights, summing exactly to total."""
    n = len(weights)
    if n == 0:
        return []
    s = float(sum(weights))
    if s == 0:
        out = [0] * n
        out[0] = total
        return out
    raw = [total * w / s for w in weights]
    fl = [math.floor(r) for r in raw]
    rem = total - sum(fl)
    order = sorted(range(n), key=lambda i: -(raw[i] - fl[i]))
    for k in range(int(rem)):
        fl[order[k % n]] += 1
    return fl


def classify_and_allocate(lines: pd.DataFrame, item_status: pd.DataFrame, parts: pd.DataFrame, active_bom_parts: set[str],
                          req_by_part_product: pd.DataFrame, has_volumes: bool, rules: dict,
                          base_qty_line: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (ledger_rows, part_alloc).

    ledger_rows: line_id, item_id, class, product_id, cents, part_id
    part_alloc:  part_id, prod_spend_cents, prod_base_qty, wavg_price, required, allocated_cents, beyond_cents
    """
    st = item_status.set_index("item_id")
    L = lines[["line_id", "item_id", "cents", "is_service", "is_shop_cc", "description", "norm_desc"]].copy()
    L["status"] = L["item_id"].map(st["status"])
    L["part_id"] = L["item_id"].map(st["part_id"])
    L["base_qty"] = base_qty_line.reindex(L.index)
    cat = parts.set_index("part_id")["category"].to_dict() if len(parts) else {}
    shop_cats = {str(c).strip().lower() for c in rules.get("shop_supply_categories", []) if str(c).strip()}
    linked = L["status"].isin(["auto", "evidence", "human"])
    part_cat_shop = L["part_id"].map(lambda p: str(cat.get(p) or "").strip().lower() in shop_cats if p else False) & linked
    cls = pd.Series("no_match", index=L.index, dtype=object)
    cls[L["status"] == "refused"] = "refused"
    cls[L["status"] == "review"] = "pending_review"
    in_bom = L["part_id"].isin(active_bom_parts)
    cls[linked & ~in_bom] = "not_in_bom"
    cls[linked & in_bom] = "production"
    cls[L["is_shop_cc"] | part_cat_shop] = "shop_supplies"
    cls[L["is_service"]] = "service"
    L["cls"] = cls

    rows = []
    other = L[L["cls"] != "production"]
    rows.append(pd.DataFrame({"line_id": other["line_id"], "item_id": other["item_id"], "class": other["cls"],
                              "product_id": None, "cents": other["cents"], "part_id": other["part_id"]}))
    prod = L[L["cls"] == "production"]
    req_tot = req_by_part_product.groupby("part_id")["required"].sum().to_dict() if len(req_by_part_product) else {}
    req_by_prod = {p: g for p, g in req_by_part_product.groupby("part_id")} if len(req_by_part_product) else {}
    alloc_rows = []
    recs: list[dict] = []
    for p, g in prod.groupby("part_id"):
        spend = int(g["cents"].sum())
        known = g[g["base_qty"].notna() & (g["base_qty"] != 0)]
        qty = float(known["base_qty"].sum()) if len(known) else 0.0
        kspend = int(known["cents"].sum()) if len(known) else 0
        wavg = (kspend / 100.0) / qty if qty > 0 else None
        req = float(req_tot.get(p, 0.0))
        if not has_volumes:
            rows.append(pd.DataFrame({"line_id": g["line_id"], "item_id": g["item_id"], "class": UNALLOCATED[0],
                                      "product_id": None, "cents": g["cents"], "part_id": p}))
            alloc_rows.append({"part_id": p, "prod_spend_cents": spend, "prod_base_qty": qty, "wavg_price": wavg,
                               "required": req, "allocated_cents": 0, "beyond_cents": 0})
            continue
        want = int(round(req * wavg * 100)) if wavg is not None and req > 0 else 0
        A = max(0, min(want, spend)) if spend > 0 else 0
        line_alloc = split_int(A, g["cents"].astype(float).tolist()) if A else [0] * len(g)
        pr = req_by_prod.get(p)
        prods = pr[pr["required"] > 0] if pr is not None else None
        for (lid, iid, c), a in zip(g[["line_id", "item_id", "cents"]].itertuples(index=False, name=None), line_alloc):
            if a and prods is not None and len(prods):
                for prod_id, x in zip(prods["product_id"], split_int(int(a), prods["required"].tolist())):
                    if x:
                        recs.append({"line_id": lid, "item_id": iid, "class": "allocated", "product_id": prod_id, "cents": x, "part_id": p})
            b = int(c) - int(a)
            if b or not a:
                recs.append({"line_id": lid, "item_id": iid, "class": "beyond_need", "product_id": None, "cents": b, "part_id": p})
        alloc_rows.append({"part_id": p, "prod_spend_cents": spend, "prod_base_qty": qty, "wavg_price": wavg,
                           "required": req, "allocated_cents": A, "beyond_cents": spend - A})
    if recs:
        rows.append(pd.DataFrame(recs))
    ledger = pd.concat([r for r in rows if len(r)], ignore_index=True) if rows else pd.DataFrame(columns=["line_id", "item_id", "class", "product_id", "cents", "part_id"])
    ledger["cents"] = ledger["cents"].astype("int64")
    part_alloc = pd.DataFrame(alloc_rows, columns=["part_id", "prod_spend_cents", "prod_base_qty", "wavg_price", "required", "allocated_cents", "beyond_cents"])
    return ledger, part_alloc


def ledger_summary(ledger: pd.DataFrame, total_cents: int, has_volumes: bool) -> dict:
    by = ledger.groupby("class")["cents"].sum().to_dict()
    classes = []
    keys = CLASSES if has_volumes else [CLASSES[0], CLASSES[1], UNALLOCATED] + CLASSES[2:]
    for k, label, group in keys:
        if not has_volumes and k in ("allocated", "beyond_need"):
            continue
        classes.append({"key": k, "label": label, "group": group, "cents": int(by.get(k, 0))})
    s = sum(c["cents"] for c in classes)
    groups = {}
    for c in classes:
        groups[c["group"]] = groups.get(c["group"], 0) + c["cents"]
    allocated = int(by.get("allocated", 0))
    return {"classes": classes, "total_cents": int(total_cents), "ledger_cents": int(s), "difference_cents": int(total_cents - s),
            "groups": groups, "allocated_cents": allocated,
            "explained_share": (allocated / total_cents) if total_cents else 0.0}
