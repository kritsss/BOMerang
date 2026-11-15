"""Turn review decisions into learned rules."""
from __future__ import annotations


def rules_from_decision(item: dict, decision: dict) -> list[dict]:
    """item: supplier_key, supplier_pn, item_key, purchase_uom. decision: action, part_id, unit_factor, base_uom."""
    out = []
    if decision["action"] == "approve":
        out.append({"kind": "xref", "value": {"supplier_key": item["supplier_key"], "supplier_pn": item.get("supplier_pn"),
                                               "item_key": item["item_key"], "part_id": decision["part_id"],
                                               "supplier_name": item.get("supplier_name")}})
        if decision.get("unit_factor"):
            out.append({"kind": "unit", "value": {"purchase_uom": item.get("purchase_uom"), "base_uom": decision.get("base_uom") or "EA",
                                                   "factor": float(decision["unit_factor"]), "item_key": item["item_key"],
                                                   "supplier_name": item.get("supplier_name")}})
    elif decision["action"] == "reject":
        out.append({"kind": "notbom", "value": {"item_key": item["item_key"], "supplier_pn": item.get("supplier_pn"),
                                                 "supplier_name": item.get("supplier_name"), "description": item.get("description")}})
    return out


def describe(rule: dict) -> str:
    v = rule["value"]
    if rule["kind"] == "xref":
        src = v.get("supplier_pn") or v.get("item_key", "").split("|d:")[-1]
        return f"{v.get('supplier_name') or v.get('supplier_key')} {src} = {v['part_id']}"
    if rule["kind"] == "unit":
        return f"1 {v.get('purchase_uom')} = {v['factor']:g} {v.get('base_uom')}" + (f" ({v.get('supplier_name')})" if v.get("supplier_name") else "")
    if rule["kind"] == "notbom":
        return f"{v.get('supplier_name')} {v.get('supplier_pn') or v.get('description') or ''}: not a BOM part"
    return str(v)
