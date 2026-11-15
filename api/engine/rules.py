"""Default, user-editable rules.

Everything here is a *starting point* shown in the Rules panel. Nothing in this
file refers to any particular dataset: it only holds generic engineering terms,
generic unit definitions and documented default thresholds.
"""
from __future__ import annotations

import copy
from typing import Any

# --- Starter synonym table -------------------------------------------------
# term -> canonical, grouped. Group names matter in one way only: if a material
# master attribute column has the same name as a group (e.g. "material"), the
# group's canonical words are added to that attribute's vocabulary so that
# values not present in the master (e.g. a carbon-steel grade on an invoice)
# can still be recognised as a *different* value.
STARTER_SYNONYMS: list[dict[str, str]] = [
    # part types (German -> English)
    {"term": "welle", "canonical": "shaft", "group": "part type"},
    {"term": "wellen", "canonical": "shaft", "group": "part type"},
    {"term": "schraube", "canonical": "screw", "group": "part type"},
    {"term": "schrauben", "canonical": "screw", "group": "part type"},
    {"term": "mutter", "canonical": "nut", "group": "part type"},
    {"term": "muttern", "canonical": "nut", "group": "part type"},
    {"term": "scheibe", "canonical": "washer", "group": "part type"},
    {"term": "unterlegscheibe", "canonical": "washer", "group": "part type"},
    {"term": "lager", "canonical": "bearing", "group": "part type"},
    {"term": "kugellager", "canonical": "bearing", "group": "part type"},
    {"term": "rillenkugellager", "canonical": "bearing", "group": "part type"},
    {"term": "dichtung", "canonical": "seal", "group": "part type"},
    {"term": "dichtring", "canonical": "seal", "group": "part type"},
    {"term": "o ring", "canonical": "oring", "group": "part type"},
    {"term": "o-ring", "canonical": "oring", "group": "part type"},
    {"term": "oring", "canonical": "oring", "group": "part type"},
    {"term": "feder", "canonical": "spring", "group": "part type"},
    {"term": "stift", "canonical": "pin", "group": "part type"},
    {"term": "bolzen", "canonical": "bolt", "group": "part type"},
    {"term": "gehaeuse", "canonical": "housing", "group": "part type"},
    {"term": "gehäuse", "canonical": "housing", "group": "part type"},
    {"term": "deckel", "canonical": "cover", "group": "part type"},
    {"term": "flansch", "canonical": "flange", "group": "part type"},
    {"term": "rohr", "canonical": "tube", "group": "part type"},
    {"term": "schlauch", "canonical": "hose", "group": "part type"},
    {"term": "ventil", "canonical": "valve", "group": "part type"},
    {"term": "kabel", "canonical": "cable", "group": "part type"},
    {"term": "stecker", "canonical": "connector", "group": "part type"},
    {"term": "halter", "canonical": "bracket", "group": "part type"},
    {"term": "blech", "canonical": "sheet", "group": "part type"},
    {"term": "zahnrad", "canonical": "gear", "group": "part type"},
    {"term": "laufrad", "canonical": "impeller", "group": "part type"},
    {"term": "kupplung", "canonical": "coupling", "group": "part type"},
    {"term": "motor", "canonical": "motor", "group": "part type"},
    # materials
    {"term": "edelstahl", "canonical": "stainless", "group": "material"},
    {"term": "rostfrei", "canonical": "stainless", "group": "material"},
    {"term": "inox", "canonical": "stainless", "group": "material"},
    {"term": "ss", "canonical": "stainless", "group": "material"},
    {"term": "1.4301", "canonical": "stainless 304", "group": "material"},
    {"term": "aisi 304", "canonical": "stainless 304", "group": "material"},
    {"term": "v2a", "canonical": "stainless 304", "group": "material"},
    {"term": "304", "canonical": "stainless 304", "group": "material"},
    {"term": "1.4401", "canonical": "stainless 316", "group": "material"},
    {"term": "1.4404", "canonical": "stainless 316", "group": "material"},
    {"term": "v4a", "canonical": "stainless 316", "group": "material"},
    {"term": "316", "canonical": "stainless 316", "group": "material"},
    {"term": "316l", "canonical": "stainless 316", "group": "material"},
    {"term": "18-8", "canonical": "stainless a2", "group": "material"},
    {"term": "a2", "canonical": "stainless a2", "group": "material"},
    {"term": "a4", "canonical": "stainless a4", "group": "material"},
    {"term": "c45", "canonical": "carbon steel c45", "group": "material"},
    {"term": "1.0503", "canonical": "carbon steel c45", "group": "material"},
    {"term": "ck45", "canonical": "carbon steel c45", "group": "material"},
    {"term": "s235", "canonical": "carbon steel s235", "group": "material"},
    {"term": "st37", "canonical": "carbon steel s235", "group": "material"},
    {"term": "kohlenstoffstahl", "canonical": "carbon steel", "group": "material"},
    {"term": "baustahl", "canonical": "carbon steel", "group": "material"},
    {"term": "stahl", "canonical": "steel", "group": "material"},
    {"term": "verzinkt", "canonical": "zinc plated", "group": "finish"},
    {"term": "galvanized", "canonical": "zinc plated", "group": "finish"},
    {"term": "messing", "canonical": "brass", "group": "material"},
    {"term": "aluminium", "canonical": "aluminum", "group": "material"},
    {"term": "alu", "canonical": "aluminum", "group": "material"},
    {"term": "kupfer", "canonical": "copper", "group": "material"},
    {"term": "bronze", "canonical": "bronze", "group": "material"},
    {"term": "gusseisen", "canonical": "cast iron", "group": "material"},
    {"term": "grauguss", "canonical": "cast iron", "group": "material"},
    {"term": "buna-n", "canonical": "nbr", "group": "material"},
    {"term": "buna n", "canonical": "nbr", "group": "material"},
    {"term": "nitrile", "canonical": "nbr", "group": "material"},
    {"term": "nitril", "canonical": "nbr", "group": "material"},
    {"term": "viton", "canonical": "fkm", "group": "material"},
    {"term": "fpm", "canonical": "fkm", "group": "material"},
    {"term": "epdm", "canonical": "epdm", "group": "material"},
    {"term": "silikon", "canonical": "silicone", "group": "material"},
    {"term": "vmq", "canonical": "silicone", "group": "material"},
    {"term": "teflon", "canonical": "ptfe", "group": "material"},
    {"term": "polyamid", "canonical": "pa", "group": "material"},
    {"term": "nylon", "canonical": "pa", "group": "material"},
    {"term": "acetal", "canonical": "pom", "group": "material"},
    {"term": "delrin", "canonical": "pom", "group": "material"},
    {"term": "kunststoff", "canonical": "plastic", "group": "material"},
    # common purchasing abbreviations
    {"term": "hsg", "canonical": "housing", "group": "part type"},
    {"term": "hous", "canonical": "housing", "group": "part type"},
    {"term": "mtr", "canonical": "motor", "group": "part type"},
    {"term": "implr", "canonical": "impeller", "group": "part type"},
    {"term": "imp", "canonical": "impeller", "group": "part type"},
    {"term": "brg", "canonical": "bearing", "group": "part type"},
    {"term": "brgs", "canonical": "bearing", "group": "part type"},
    {"term": "shft", "canonical": "shaft", "group": "part type"},
    {"term": "scr", "canonical": "screw", "group": "part type"},
    {"term": "hcs", "canonical": "hex cap screw", "group": "part type"},
    {"term": "shcs", "canonical": "socket head cap screw", "group": "part type"},
    {"term": "hex hd", "canonical": "hex", "group": "part type"},
    {"term": "wshr", "canonical": "washer", "group": "part type"},
    {"term": "brkt", "canonical": "bracket", "group": "part type"},
    {"term": "assy", "canonical": "assembly", "group": "part type"},
    {"term": "vlv", "canonical": "valve", "group": "part type"},
    {"term": "gskt", "canonical": "gasket", "group": "part type"},
    {"term": "mech seal", "canonical": "mechanical seal", "group": "part type"},
    {"term": "gry irn", "canonical": "cast iron", "group": "material"},
    {"term": "gray iron", "canonical": "cast iron", "group": "material"},
    {"term": "grey iron", "canonical": "cast iron", "group": "material"},
    {"term": "gg25", "canonical": "cast iron", "group": "material"},
    {"term": "duct iron", "canonical": "ductile iron", "group": "material"},
    {"term": "ggg40", "canonical": "ductile iron", "group": "material"},
    {"term": "brz", "canonical": "bronze", "group": "material"},
    {"term": "alum", "canonical": "aluminum", "group": "material"},
    {"term": "stl", "canonical": "steel", "group": "material"},
    {"term": "svc", "canonical": "service", "group": "general"},
    # general words
    {"term": "ersatzteil", "canonical": "spare", "group": "general"},
    {"term": "ersatz", "canonical": "spare", "group": "general"},
    {"term": "gewaehrleistung", "canonical": "warranty", "group": "general"},
    {"term": "gewährleistung", "canonical": "warranty", "group": "general"},
    {"term": "garantie", "canonical": "warranty", "group": "general"},
    {"term": "wartung", "canonical": "maintenance", "group": "general"},
    {"term": "instandhaltung", "canonical": "maintenance", "group": "general"},
    {"term": "stueck", "canonical": "pc", "group": "general"},
    {"term": "stück", "canonical": "pc", "group": "general"},
    {"term": "stk", "canonical": "pc", "group": "general"},
    {"term": "laenge", "canonical": "length", "group": "general"},
    {"term": "länge", "canonical": "length", "group": "general"},
    {"term": "durchmesser", "canonical": "diameter", "group": "general"},
    {"term": "dia", "canonical": "diameter", "group": "general"},
    {"term": "shore a", "canonical": "shore", "group": "general"},
    {"term": "sh a", "canonical": "shore", "group": "general"},
    {"term": "shr", "canonical": "shore", "group": "general"},
]

# --- Default unit conversions ---------------------------------------------
# Unit aliases (purchase unit spelling -> canonical unit code)
UNIT_ALIASES: dict[str, str] = {
    "ea": "EA", "each": "EA", "pc": "EA", "pcs": "EA", "piece": "EA", "pieces": "EA",
    "st": "EA", "stk": "EA", "stck": "EA", "stück": "EA", "stueck": "EA", "un": "EA", "unit": "EA",
    "units": "EA", "nos": "EA", "no": "EA", "ct": "EA",
    "c": "C", "h": "C", "hundred": "C", "per100": "C", "100": "C",
    "m1000": "TH", "th": "TH", "mil": "TH", "thousand": "TH", "per1000": "TH", "k": "TH", "1000": "TH",
    "dz": "DZ", "dozen": "DZ", "dzn": "DZ",
    "pk": "PK", "pack": "PK", "pkg": "PK", "pak": "PK",
    "bx": "BX", "box": "BX", "ctn": "CTN", "carton": "CTN", "bag": "BAG", "set": "SET",
    "mm": "MM", "cm": "CM", "m": "M", "meter": "M", "metre": "M", "mtr": "M",
    "in": "IN", "inch": "IN", "\"": "IN", "ft": "FT", "foot": "FT", "feet": "FT",
    "g": "G", "gram": "G", "kg": "KG", "kilo": "KG", "lb": "LB", "lbs": "LB", "oz": "OZ", "t": "TON",
    "l": "L", "ltr": "L", "liter": "L", "litre": "L", "ml": "ML",
}

# Dimension families with factor to a family reference unit
UNIT_FAMILIES: dict[str, dict[str, float]] = {
    "count": {"EA": 1.0, "C": 100.0, "TH": 1000.0, "DZ": 12.0},
    "length": {"MM": 0.001, "CM": 0.01, "M": 1.0, "IN": 0.0254, "FT": 0.3048},
    "mass": {"G": 0.001, "KG": 1.0, "LB": 0.45359237, "OZ": 0.028349523125, "TON": 1000.0},
    "volume": {"ML": 0.001, "L": 1.0},
}

UNIT_INFERENCE_FACTORS = [1, 6, 10, 12, 24, 50, 100, 144, 250, 500, 1000]

DEFAULT_RULES: dict[str, Any] = {
    "synonyms": STARTER_SYNONYMS,
    # {category: [attribute columns]}; "*" applies to every category without its own entry
    "hard_attributes": {"*": []},
    # user-defined conversions, e.g. {"purchase_uom": "BX", "base_uom": "EA", "factor": 100}
    "unit_conversions": [],
    "price_band": {"low": 0.6, "high": 1.6},
    "thresholds": {
        "auto_link_min_text": 0.30,   # text similarity a spec-rule link must reach to auto-link
        "balance_margin": 0.25,       # quantity-balance margin to resolve an ambiguous item
        "candidate_top_k": 12,        # candidates compared per item
        "min_similarity": 0.20,       # below this nothing is considered a candidate
        "review_money_floor": 0.3,    # money at stake floor for review items
    },
    "service_keywords": ["spare", "service", "warranty", "repair", "replacement", "aftermarket", "rma"],
    "shop_supply_cost_centers": ["maintenance", "mro", "facility", "facilities", "workshop", "tooling", "cleaning"],
    "shop_supply_categories": [],
    "shop_supply_keywords": [],
}


def default_rules() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_RULES)


def merge_rules(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Fill any missing keys of a stored rule set with defaults (forward compatible)."""
    r = default_rules()
    if not stored:
        return r
    for k, v in stored.items():
        if k == "thresholds" and isinstance(v, dict):
            r["thresholds"].update(v)
        elif k == "price_band" and isinstance(v, dict):
            r["price_band"].update(v)
        else:
            r[k] = v
    return r


def hard_attributes_for(rules: dict[str, Any], category: str | None) -> list[str]:
    ha = rules.get("hard_attributes") or {}
    if category is not None and str(category) in ha:
        return list(ha[str(category)])
    return list(ha.get("*", []))


def suggest_hard_attributes(attribute_columns: list[str]) -> list[str]:
    """Suggest (never assume) hard attributes from column names: material and main dimension."""
    keys_mat = ("material", "werkstoff", "matl", "grade", "alloy")
    keys_dim = ("dimension", "size", "dim", "groesse", "größe", "abmessung", "diameter", "durchmesser", "thread")
    out = []
    for c in attribute_columns:
        lc = c.lower()
        if any(k in lc for k in keys_mat) or any(k in lc for k in keys_dim):
            out.append(c)
    return out
