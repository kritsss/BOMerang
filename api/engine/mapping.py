"""Column mapping: canonical schema, auto-suggestions from header similarity and sample values."""
from __future__ import annotations

import re

import pandas as pd
from rapidfuzz import fuzz

from .normalize import basic_clean, canon_unit

# file type -> list of (field, required, header aliases)
SCHEMA: dict[str, list[tuple[str, bool, list[str]]]] = {
    "bom": [
        ("parent_id", True, ["parent", "parent id", "parent part", "assembly", "product", "product id", "top item", "baugruppe", "vater", "header material"]),
        ("component_id", True, ["component", "component id", "child", "part", "part id", "part number", "material", "item", "komponente", "teil", "sachnummer"]),
        ("qty_per_parent", True, ["qty", "quantity", "qty per", "qty per parent", "usage", "menge", "anzahl", "per"]),
        ("uom", False, ["uom", "unit", "unit of measure", "me", "einheit", "base unit"]),
        ("description_as_written", False, ["description", "desc", "text", "component description", "bezeichnung", "beschreibung", "name"]),
        ("revision", False, ["rev", "revision", "version", "stand"]),
    ],
    "spend": [
        ("line_id", False, ["line id", "line", "id", "invoice line", "row id", "position", "transaction id"]),
        ("supplier_id", False, ["supplier id", "vendor id", "vendor number", "supplier number", "kreditor", "lieferantennummer"]),
        ("supplier_name", False, ["supplier", "supplier name", "vendor", "vendor name", "lieferant", "lieferantenname"]),
        ("description", True, ["description", "item description", "text", "line description", "material description", "bezeichnung", "beschreibung", "kurztext", "item"]),
        ("qty", True, ["qty", "quantity", "invoiced qty", "menge", "anzahl", "volume"]),
        ("purchase_uom", False, ["uom", "unit", "purchase uom", "order unit", "me", "einheit", "bestellmengeneinheit"]),
        ("unit_price", False, ["unit price", "price", "net price", "preis", "einzelpreis", "price per unit"]),
        ("amount", False, ["amount", "total", "net amount", "spend", "value", "line total", "betrag", "wert", "net value"]),
        ("currency", False, ["currency", "curr", "ccy", "waehrung", "währung"]),
        ("invoice_date", False, ["invoice date", "date", "posting date", "rechnungsdatum", "datum", "doc date"]),
        ("invoice_month", False, ["month", "period", "invoice month", "monat", "periode"]),
        ("supplier_part_no", False, ["supplier part", "supplier part no", "vendor part", "vendor material", "mpn", "supplier pn", "lieferantenmaterial", "artikelnummer"]),
        ("material_id_if_known", False, ["material id", "material", "part id", "internal part", "material number", "materialnummer"]),
        ("cost_center", False, ["cost center", "cost centre", "kostenstelle", "cc", "department"]),
        ("po_number", False, ["po", "po number", "purchase order", "bestellung", "bestellnummer"]),
        ("supplier_country", False, ["country", "supplier country", "land"]),
    ],
    "products": [
        ("product_id", True, ["product", "product id", "model", "sku", "produkt", "material"]),
        ("name", False, ["name", "product name", "description", "bezeichnung"]),
        ("family", False, ["family", "product family", "line", "group", "familie"]),
        ("status", False, ["status", "lifecycle", "active"]),
    ],
    "master": [
        ("part_id", True, ["part", "part id", "material", "material number", "item", "sachnummer", "materialnummer", "part number"]),
        ("description", False, ["description", "desc", "material description", "bezeichnung", "text", "name"]),
        ("category", False, ["category", "material group", "group", "class", "warengruppe", "materialgruppe", "commodity"]),
        ("base_uom", False, ["base uom", "uom", "unit", "basismengeneinheit", "einheit"]),
        ("standard_cost", False, ["standard cost", "std cost", "cost", "standardpreis", "price", "standard price"]),
        ("currency", False, ["currency", "waehrung", "währung"]),
    ],
    "volumes": [
        ("product_id", True, ["product", "product id", "model", "sku", "produkt"]),
        ("period", False, ["period", "month", "year", "date", "monat", "jahr"]),
        ("units_built", True, ["units built", "units", "qty", "quantity", "volume", "production", "menge", "produced"]),
    ],
    "suppliers": [
        ("supplier_id", True, ["supplier id", "vendor id", "id", "kreditor"]),
        ("supplier_name", False, ["supplier name", "name", "vendor", "lieferant"]),
        ("country", False, ["country", "land"]),
    ],
    "conversions": [
        ("purchase_uom", True, ["purchase uom", "from", "from unit", "alt uom", "order unit"]),
        ("base_uom", True, ["base uom", "to", "to unit", "base unit"]),
        ("factor", True, ["factor", "multiplier", "conversion", "faktor"]),
    ],
    "fx": [
        ("currency", True, ["currency", "from", "ccy", "waehrung"]),
        ("rate_to_display_currency", True, ["rate", "fx", "rate to display currency", "exchange rate", "kurs"]),
        ("period", False, ["period", "month", "date"]),
    ],
    "xrefs": [
        ("supplier_id", False, ["supplier id", "vendor id", "kreditor"]),
        ("supplier_name", False, ["supplier", "supplier name", "vendor"]),
        ("supplier_part_no", True, ["supplier part", "supplier part no", "vendor part", "mpn", "supplier pn"]),
        ("part_id", True, ["part", "part id", "material", "internal part", "material number"]),
        ("approved_by", False, ["approved by", "by", "owner"]),
        ("approved_on", False, ["approved on", "date", "on"]),
    ],
    "answer_key": [
        ("line_id", True, ["line id", "line", "id"]),
        ("true_part_id", True, ["true part id", "true part", "part id", "answer", "truth", "part"]),
        ("class", False, ["class", "label", "type"]),
    ],
}

FILE_TYPE_LABEL = {"bom": "BOM", "spend": "Spend lines", "products": "Products", "master": "Material master", "volumes": "Production volumes",
                   "suppliers": "Suppliers", "conversions": "Unit conversions", "fx": "FX rates", "xrefs": "Approved cross-references",
                   "answer_key": "Answer key (proof only)"}


def _hnorm(h: str) -> str:
    h = basic_clean(str(h)).replace("_", " ")
    return re.sub(r"\s+", " ", h).strip()


def _value_bonus(field: str, s: pd.Series) -> float:
    v = s.dropna().astype(str).head(30)
    if v.empty:
        return 0.0
    num = pd.to_numeric(v.str.replace(",", ".", regex=False), errors="coerce").notna().mean()
    if field in ("qty", "qty_per_parent", "unit_price", "amount", "standard_cost", "units_built", "factor", "rate_to_display_currency"):
        return 15 * num - 10 * (1 - num)
    if field == "currency":
        return 20 if v.str.fullmatch(r"[A-Za-z]{3}").mean() > 0.8 else -10
    if field in ("uom", "purchase_uom", "base_uom"):
        return 15 if v.map(lambda x: len(x) <= 6).mean() > 0.8 and num < 0.5 else -10
    if field in ("description", "description_as_written"):
        return 10 if v.str.len().mean() > 12 and num < 0.2 else -5
    if field in ("invoice_date",):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return 10 if pd.to_datetime(v, errors="coerce").notna().mean() > 0.8 else -10
    return 0.0


def suggest_mapping(df: pd.DataFrame, file_type: str) -> dict[str, str | None]:
    cols = list(df.columns)
    scores = []
    for field, _, aliases in SCHEMA[file_type]:
        cands = [field.replace("_", " ")] + aliases
        for c in cols:
            hn = _hnorm(c)
            s = max(fuzz.ratio(hn, a) for a in cands)
            s = max(s, max((fuzz.token_set_ratio(hn, a) - 8) for a in cands))
            if hn in cands:
                s = 100
            s += _value_bonus(field, df[c])
            scores.append((s, field, c))
    scores.sort(reverse=True)
    used_f, used_c, out = set(), set(), {f: None for f, _, _ in SCHEMA[file_type]}
    for s, f, c in scores:
        if s < 70 or f in used_f or c in used_c:
            continue
        out[f] = c
        used_f.add(f)
        used_c.add(c)
    return out


def suggest_file_type(df: pd.DataFrame, sheet_name: str = "") -> str:
    best, best_t = -1.0, "spend"
    name = basic_clean(sheet_name)
    for t in SCHEMA:
        m = suggest_mapping(df, t)
        req = [f for f, r, _ in SCHEMA[t] if r]
        hit_req = sum(1 for f in req if m.get(f))
        hit_all = sum(1 for v in m.values() if v)
        score = 3 * hit_req / max(len(req), 1) + hit_all * 0.2 - (2 if hit_req < len(req) else 0)
        label = basic_clean(FILE_TYPE_LABEL[t])
        if name and (t in name or label.split()[0] in name):
            score += 2
        if score > best:
            best, best_t = score, t
    return best_t


def apply_mapping(df: pd.DataFrame, file_type: str, mapping: dict[str, str | None], attribute_columns: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Return (canonical frame, errors)."""
    errors = []
    out = pd.DataFrame(index=df.index)
    for field, req, _ in SCHEMA[file_type]:
        src = mapping.get(field)
        if src and src in df.columns:
            out[field] = df[src]
        elif req:
            errors.append(f"Required column '{field}' is not mapped.")
    if file_type == "spend":
        if not (mapping.get("supplier_id") or mapping.get("supplier_name")):
            errors.append("Map supplier_id or supplier_name.")
        if not (mapping.get("unit_price") or mapping.get("amount")):
            errors.append("Map unit_price or amount (the other is derived).")
        if "currency" not in out:
            out["currency"] = None
    if file_type == "master":
        for a in attribute_columns or []:
            if a in df.columns:
                out[a] = df[a]
    out = out.dropna(how="all")
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].map(lambda v: v.strip() if isinstance(v, str) else v)
    return out, errors


def unit_values(df: pd.DataFrame, col: str | None) -> list[str]:
    if not col or col not in df:
        return []
    return sorted({str(canon_unit(v)) for v in df[col].dropna()})
