"""Small fixtures created in code. Never imported by the running app."""
import pandas as pd

MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]


def bom():
    return pd.DataFrame([
        ("P-A", "SUB-1", 1, "EA", "Subassembly"),
        ("P-A", "PRT-SH1", 1, "EA", "Shaft"),
        ("P-A", "PRT-OR1", 2, "EA", "O-ring"),
        ("SUB-1", "PRT-SC1", 4, "EA", "Screw"),
        ("P-B", "PRT-SH1", 1, "EA", "Shaft"),
        ("P-B", "PRT-OR2", 2, "EA", "O-ring"),
        ("P-B", "PRT-SC1", 4, "EA", "Screw"),
        ("P-OLD", "PRT-X9", 1, "EA", "Bracket"),
    ], columns=["parent_id", "component_id", "qty_per_parent", "uom", "description_as_written"])


def products():
    return pd.DataFrame([("P-A", "Pump A", "Pumps", "active"), ("P-B", "Pump B", "Pumps", "active"),
                         ("P-OLD", "Old pump", "Pumps", "discontinued")], columns=["product_id", "name", "family", "status"])


def master():
    return pd.DataFrame([
        ("PRT-SH1", "Shaft stainless", "Shafts", "EA", 3.00, "Stainless 1.4301", "8x120", None),
        ("PRT-OR1", "O-ring", "Seals", "EA", 0.15, "NBR", "20x2", "70"),
        ("PRT-OR2", "O-ring", "Seals", "EA", 0.16, "NBR", "20x2", None),
        ("PRT-OR3", "O-ring", "Seals", "EA", 0.40, "FKM", "20x2", "90"),
        ("PRT-SC1", "Screw", "Fasteners", "EA", 0.05, "A2", "M6x20", None),
        ("PRT-X9", "Bracket", "Brackets", "EA", 2.00, "S235", "40x40", None),
    ], columns=["part_id", "description", "category", "base_uom", "standard_cost", "material", "size", "hardness"])


def volumes():
    rows = []
    for m in MONTHS:
        rows.append(("P-A", m, 1000))
        rows.append(("P-B", m, 500))
    return pd.DataFrame(rows, columns=["product_id", "period", "units_built"])


def spend():
    rows = [
        # line, supplier, pn, desc, qty, uom, price, cur, month, cc, material id
        ("L1", "S1", "S1-SH8", "Welle 8x120 Edelstahl 1.4301", 6000, "EA", 3.10, "USD", "2026-02", "Production", None),
        ("L2", "S2", "B-88", "Shaft SS304 8 x 120mm", 2900, "EA", 3.00, "EUR", "2026-03", "Production", None),
        ("L3", "S1", "S1-C45", "Welle 8x120 C45", 500, "EA", 1.90, "USD", "2026-03", "Production", None),
        ("L4", "S3", "OR-90", "O-Ring 20x2 NBR 90 Shore", 6000, "EA", 0.16, "USD", "2026-02", "Production", None),
        ("L5", "S3", "OR-70", "O-Ring 20x2 NBR 70 Shore", 12000, "EA", 0.15, "USD", "2026-02", "Production", None),
        ("L6", "S4", "SC-620", "Screw M6x20 stainless A2", 360, "BX", 5.00, "USD", "2026-03", "Production", None),
        ("L7", "S5", None, "Bracket", 50, "EA", 2.10, "USD", "2026-01", "Production", "PRT-X9"),
        ("L8", "S1", "S1-SH8", "Welle 8x120 1.4301 Ersatzteil", 200, "EA", 4.60, "USD", "2026-04", "Service", None),
        ("L9", "S6", None, "Cleaning cloth", 10, "PK", 12.00, "USD", "2026-04", "Maintenance", None),
        ("L10", "S7", None, "Consulting fee", 1, "EA", 1500.00, "USD", "2026-05", "Admin", None),
        ("L11", "S2", "B-88", "Shaft SS304 8 x 120mm", 100, "EA", 3.00, "EUR", "2026-05", "Production", None),
        ("L12", "S8", "XR-1", "Fastener pack", 100, "EA", 0.05, "USD", "2026-05", "Production", None),
    ]
    return pd.DataFrame(rows, columns=["line_id", "supplier_name", "supplier_part_no", "description", "qty", "purchase_uom",
                                       "unit_price", "currency", "invoice_month", "cost_center", "material_id_if_known"])


def fx():
    return pd.DataFrame([("EUR", 1.10)], columns=["currency", "rate_to_display_currency"])


def xrefs():
    return pd.DataFrame([("S8", "XR-1", "PRT-SC1", "buyer", "2026-01-01")],
                        columns=["supplier_name", "supplier_part_no", "part_id", "approved_by", "approved_on"])


def answer_key():
    return pd.DataFrame([("L1", "PRT-SH1"), ("L2", "PRT-SH1"), ("L3", "NONE"), ("L4", "PRT-OR2"), ("L5", "PRT-OR1"),
                         ("L6", "PRT-SC1"), ("L7", "PRT-X9"), ("L8", "PRT-SH1"), ("L9", "NONE"), ("L10", "NONE"),
                         ("L11", "PRT-SH1"), ("L12", "PRT-SC1")], columns=["line_id", "true_part_id"])


def inputs(**over):
    from engine.pipeline import Inputs
    from engine.rules import default_rules
    rules = default_rules()
    rules["hard_attributes"] = {"*": ["material", "size", "hardness"]}
    kw = dict(bom=bom(), spend=spend(), products=products(), master=master(), volumes=volumes(), fx=fx(), xrefs=xrefs(),
              attribute_columns=["material", "size", "hardness"], display_currency="USD", rules=rules)
    kw.update(over)
    return Inputs(**kw)
