"""Spend line preparation and grouping into supplier items (vectorized)."""
from __future__ import annotations

import hashlib
import re

import numpy as np
import pandas as pd

from .normalize import basic_clean, canon_unit, normalize_text


def _s(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df:
        return df[col]
    return pd.Series([None] * len(df), index=df.index, dtype=object)


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in ("", "nan", "NaN", "None", "NaT", "<NA>")


def _clean_str(series: pd.Series) -> pd.Series:
    """Strings stripped; anything blank becomes a real None (never NaN, never the text 'nan')."""
    vals = [None if _blank(v) else str(v).strip() for v in series.tolist()]
    return pd.Series(vals, index=series.index, dtype=object)


def keyword_mask(text: pd.Series, keywords: list[str]) -> pd.Series:
    kws = [basic_clean(k) for k in keywords or [] if basic_clean(k)]
    if not kws:
        return pd.Series(False, index=text.index)
    pat = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(k) for k in kws) + r")", re.I)
    return text.fillna("").map(lambda t: bool(pat.search(t)))


def prepare_lines(spend: pd.DataFrame, rate_fn, syn_key, rules: dict) -> pd.DataFrame:
    """Canonical spend -> enriched lines (display currency, cents, flags, item key)."""
    df = spend.copy().reset_index(drop=True)
    n = len(df)
    out = pd.DataFrame(index=df.index)
    lid = _clean_str(_s(df, "line_id"))
    out["line_id"] = [v if v else f"L{i+1:06d}" for i, v in enumerate(lid.tolist())]
    if out["line_id"].duplicated().any():
        out["line_id"] = out["line_id"] + "#" + out.groupby("line_id").cumcount().astype(str)
    sid = _clean_str(_s(df, "supplier_id"))
    sname = _clean_str(_s(df, "supplier_name"))
    out["supplier_name"] = [a or b or "(unknown supplier)" for a, b in zip(sname.tolist(), sid.tolist())]
    out["supplier_key"] = [basic_clean(a) if a else basic_clean(b or "unknown") for a, b in zip(sid.tolist(), sname.tolist())]
    out["supplier_pn"] = _clean_str(_s(df, "supplier_part_no"))
    out["description"] = _clean_str(_s(df, "description")).fillna("")
    out["qty"] = pd.to_numeric(_s(df, "qty"), errors="coerce")
    up = pd.to_numeric(_s(df, "unit_price"), errors="coerce")
    amt = pd.to_numeric(_s(df, "amount"), errors="coerce")
    amt = amt.where(amt.notna(), out["qty"] * up)
    up = up.where(up.notna(), amt / out["qty"].replace(0, np.nan))
    out["unit_price"] = up
    out["amount"] = amt.fillna(0.0)
    out["currency"] = _clean_str(_s(df, "currency")).fillna("").str.upper()
    out["purchase_uom"] = _clean_str(_s(df, "purchase_uom"))
    out["purchase_uom_c"] = out["purchase_uom"].map(canon_unit)
    # month
    month = _clean_str(_s(df, "invoice_month"))
    dates = pd.to_datetime(_s(df, "invoice_date"), errors="coerce")
    m2 = dates.dt.strftime("%Y-%m")
    month = month.where(month.notna(), m2.where(m2.notna(), None))
    month = month.map(lambda v: _norm_month(v) if v else None)
    out["month"] = month
    out["cost_center"] = _clean_str(_s(df, "cost_center"))
    out["po_number"] = _clean_str(_s(df, "po_number"))
    out["supplier_country"] = _clean_str(_s(df, "supplier_country"))
    out["material_id_if_known"] = _clean_str(_s(df, "material_id_if_known"))
    # currency conversion
    rates = [rate_fn(c, m) for c, m in zip(out["currency"], out["month"])]
    out["fx_rate"] = pd.Series(rates, index=out.index, dtype="float64")
    out["amount_disp"] = out["amount"] * out["fx_rate"]
    out["cents"] = np.round(out["amount_disp"].fillna(0.0) * 100).astype("int64")
    out["unit_price_disp"] = out["unit_price"] * out["fx_rate"]
    # text
    out["norm_desc"] = out["description"].map(lambda t: normalize_text(t, syn_key))
    # flags
    cc = out["cost_center"].fillna("").map(basic_clean)
    svc_kw = rules.get("service_keywords", [])
    out["is_service"] = keyword_mask(cc, svc_kw) | keyword_mask(out["norm_desc"], svc_kw) | keyword_mask(out["description"].map(basic_clean), svc_kw)
    out["is_shop_cc"] = keyword_mask(cc, rules.get("shop_supply_cost_centers", [])) | keyword_mask(out["norm_desc"], rules.get("shop_supply_keywords", []))
    # item key
    pn_norm = [None if _blank(v) else (re.sub(r"[^a-z0-9]", "", str(v).lower()) or None) for v in out["supplier_pn"].tolist()]
    out["item_key"] = [f"{s}|pn:{p}" if p else f"{s}|d:{d}" for s, p, d in zip(out["supplier_key"], pn_norm, out["norm_desc"])]
    out["item_id"] = out["item_key"].map(lambda k: "I" + hashlib.sha1(k.encode()).hexdigest()[:10])
    return out


def _norm_month(v: str) -> str | None:
    s = str(v).strip()
    m = re.match(r"^(\d{4})[-/.]?(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    d = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(d) else d.strftime("%Y-%m")


def _mode(s: pd.Series):
    s = s.dropna()
    if s.empty:
        return None
    return s.value_counts().index[0]


def _group_mode(df: pd.DataFrame, key: str, col: str) -> pd.Series:
    """Most frequent non-null value per group (vectorized)."""
    sub = df[[key, col]].dropna()
    if sub.empty:
        return pd.Series(dtype=object)
    cnt = sub.groupby([key, col], sort=False).size().reset_index(name="_n")
    cnt = cnt.sort_values([key, "_n"], ascending=[True, False]).drop_duplicates(key)
    return cnt.set_index(key)[col]


def build_items(lines: pd.DataFrame) -> pd.DataFrame:
    g = lines.groupby("item_id", sort=False)
    items = pd.DataFrame({
        "item_key": g["item_key"].first(),
        "supplier_key": g["supplier_key"].first(),
        "supplier_name": g["supplier_name"].first(),
        "n_lines": g.size(),
        "spend_cents": g["cents"].sum(),
    })
    for c in ("supplier_pn", "description", "norm_desc", "material_id_if_known"):
        items[c] = _group_mode(lines, "item_id", c).reindex(items.index)
    items["description"] = items["description"].fillna("")
    items["norm_desc"] = items["norm_desc"].fillna("")
    prod = lines[~lines["is_service"]]
    pg = prod.groupby("item_id")
    items["prod_spend_cents"] = pg["cents"].sum().reindex(items.index).fillna(0).astype("int64")
    items["purchase_uom"] = _group_mode(lines, "item_id", "purchase_uom").reindex(items.index)
    items["purchase_uom_c"] = _group_mode(lines, "item_id", "purchase_uom_c").reindex(items.index)
    # quantities by purchase unit (production lines only), used for conversion per candidate part
    q = prod.assign(_u=prod["purchase_uom_c"].fillna("")).groupby(["item_id", "_u"])["qty"].sum().reset_index()
    qty_by_uom: dict[str, dict[str, float]] = {}
    for iid, u, v in zip(q["item_id"], q["_u"], q["qty"]):
        qty_by_uom.setdefault(iid, {})[u] = float(v) if pd.notna(v) else 0.0
    items["qty_by_uom"] = [qty_by_uom.get(i, {}) for i in items.index]
    items["is_service_only"] = items["prod_spend_cents"] == 0
    items = items.reset_index()
    return items
