"""BOM explosion (multi-level) and required quantities."""
from __future__ import annotations

import pandas as pd

MAX_DEPTH = 25


def top_level_products(bom: pd.DataFrame, products: pd.DataFrame | None) -> pd.DataFrame:
    """Product list with status. From the products file if given, else BOM parents that are never components."""
    if products is not None and len(products):
        p = products.copy()
        p["product_id"] = p["product_id"].astype(str)
        if "name" not in p:
            p["name"] = p["product_id"]
        p["name"] = p["name"].fillna(p["product_id"]).astype(str)
        if "status" not in p:
            p["status"] = "active"
        p["status"] = p["status"].fillna("active").astype(str).str.lower()
        if "family" not in p:
            p["family"] = None
        return p[["product_id", "name", "family", "status"]].drop_duplicates("product_id")
    parents = set(bom["parent_id"].astype(str))
    comps = set(bom["component_id"].astype(str))
    tops = sorted(parents - comps)
    return pd.DataFrame({"product_id": tops, "name": tops, "family": None, "status": "active"})


def explode(bom: pd.DataFrame, product_ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (tree, leaves).

    tree:   product_id, level, seq, parent_id, component_id, qty_per_parent, ext_qty, is_leaf, uom, description
    leaves: product_id, part_id, qty_per_unit  (summed over all paths)
    """
    b = bom.copy()
    b["parent_id"] = b["parent_id"].astype(str)
    b["component_id"] = b["component_id"].astype(str)
    b["qty_per_parent"] = pd.to_numeric(b["qty_per_parent"], errors="coerce").fillna(0.0)
    for c in ("uom", "description_as_written"):
        if c not in b:
            b[c] = None
    b = b.reset_index(drop=True)
    b["_ord"] = range(len(b))
    parents = set(b["parent_id"])

    frontier = pd.DataFrame({"product_id": product_ids, "node": product_ids, "mult": 1.0, "path": [f"{i:06d}" for i in range(len(product_ids))]})
    rows = []
    for level in range(1, MAX_DEPTH + 1):
        if frontier.empty:
            break
        nxt = frontier.merge(b, left_on="node", right_on="parent_id", how="inner")
        if nxt.empty:
            break
        nxt["ext_qty"] = nxt["mult"] * nxt["qty_per_parent"]
        nxt["level"] = level
        nxt["path"] = nxt["path"] + "/" + nxt["_ord"].map(lambda x: f"{x:06d}")
        nxt["is_leaf"] = ~nxt["component_id"].isin(parents)
        rows.append(nxt[["product_id", "level", "path", "parent_id", "component_id", "qty_per_parent", "ext_qty", "is_leaf", "uom", "description_as_written"]])
        # guard against cycles: do not descend into a node already on the path
        frontier = nxt.loc[~nxt["is_leaf"], ["product_id", "component_id", "ext_qty", "path"]].rename(columns={"component_id": "node", "ext_qty": "mult"})
    if rows:
        tree = pd.concat(rows, ignore_index=True).sort_values(["product_id", "path"]).reset_index(drop=True)
    else:
        tree = pd.DataFrame(columns=["product_id", "level", "path", "parent_id", "component_id", "qty_per_parent", "ext_qty", "is_leaf", "uom", "description_as_written"])
    tree["seq"] = range(len(tree))
    leaves = (tree[tree["is_leaf"]].groupby(["product_id", "component_id"], as_index=False)["ext_qty"].sum()
              .rename(columns={"component_id": "part_id", "ext_qty": "qty_per_unit"}))
    return tree, leaves


def required_quantities(leaves: pd.DataFrame, volumes: pd.DataFrame | None, active_products: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (req_by_part_product, req_by_part_period).

    req_by_part_product: part_id, product_id, qty_per_unit, units_built, required
    req_by_part_period:  part_id, period, required
    """
    if volumes is None or not len(volumes):
        return (pd.DataFrame(columns=["part_id", "product_id", "qty_per_unit", "units_built", "required"]),
                pd.DataFrame(columns=["part_id", "period", "required"]))
    v = volumes.copy()
    v["product_id"] = v["product_id"].astype(str)
    v["units_built"] = pd.to_numeric(v["units_built"], errors="coerce").fillna(0.0)
    if "period" not in v:
        v["period"] = "all"
    v["period"] = v["period"].astype(str)
    v = v[v["product_id"].isin(active_products)]
    lv = leaves[leaves["product_id"].isin(active_products)]
    per = lv.merge(v, on="product_id", how="inner")
    per["required"] = per["qty_per_unit"] * per["units_built"]
    by_period = per.groupby(["part_id", "period"], as_index=False)["required"].sum()
    tot_units = v.groupby("product_id", as_index=False)["units_built"].sum()
    bp = lv.merge(tot_units, on="product_id", how="left").fillna({"units_built": 0.0})
    bp["required"] = bp["qty_per_unit"] * bp["units_built"]
    return bp[["part_id", "product_id", "qty_per_unit", "units_built", "required"]], by_period
