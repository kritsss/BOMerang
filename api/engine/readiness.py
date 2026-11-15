"""Data readiness: which features are on, which are off, and how to turn them on."""
from __future__ import annotations

import pandas as pd

from .normalize import canon_unit, conversion_factor


def _has(df, col):
    return df is not None and col in df and df[col].notna().any() and (df[col].astype(str).str.strip() != "").any()


def readiness(data: dict[str, pd.DataFrame | None], display_currency: str, fx_overrides: dict, attribute_columns: list[str],
              hard_attributes: dict, ai_on: bool, rules: dict) -> dict:
    bom, spend = data.get("bom"), data.get("spend")
    feats = []

    def add(key, label, on, why, how=""):
        feats.append({"key": key, "label": label, "on": bool(on), "why": why, "how": "" if on else how})

    have_bom = bom is not None and len(bom) > 0
    have_spend = spend is not None and len(spend) > 0
    add("matching", "Linking spend to BOM parts", have_bom and have_spend,
        "BOM and spend loaded." if have_bom and have_spend else "Needs a BOM and a spend file.",
        "Upload a BOM and a spend file. Only these two are required.")
    master = data.get("master")
    hard_any = any(v for v in (hard_attributes or {}).values())
    add("spec", "Spec rules (attribute checks and refusals)", master is not None and len(master) > 0 and bool(attribute_columns) and hard_any,
        "Material master with attributes and hard attributes set." if master is not None and attribute_columns and hard_any else
        ("No material master: parts are matched on BOM descriptions only." if master is None else
         "No hard attributes chosen, so nothing can be refused or confirmed by attributes."),
        "Upload a material master with attribute columns and mark the hard ones in Rules." if master is None else "Open Rules and choose hard attributes per category.")
    vol = data.get("volumes")
    have_vol = vol is not None and len(vol) > 0
    add("allocation", "Allocation to products and the spend explainer", have_vol,
        "Production volumes loaded." if have_vol else "No production volumes: spend cannot be allocated to products.",
        "Upload production volumes (product, period, units built).")
    add("balance", "Quantity balance (do the quantities add up?)", have_vol,
        "Uses production volumes." if have_vol else "Needs production volumes.", "Upload production volumes.")
    monthly = have_spend and (_has(spend, "invoice_date") or _has(spend, "invoice_month"))
    vol_monthly = have_vol and "period" in vol and vol["period"].astype(str).nunique() >= 4
    add("timing", "Timing check", monthly and vol_monthly,
        "Monthly purchases and monthly volumes loaded." if monthly and vol_monthly else
        ("No monthly purchase dates." if not monthly else "Volumes are not monthly (need at least 4 periods)."),
        "Map invoice_date or invoice_month and upload monthly volumes.")
    cc = have_spend and _has(spend, "cost_center")
    add("service_cc", "Service and shop-supply spend by cost center", cc,
        "Cost centers mapped." if cc else "No cost centers: service spend cannot be separated by label (descriptions are still checked).",
        "Map a cost_center column in the spend file.")
    add("price", "Price gate", have_spend, "Expected prices come from certain links, else standard cost.", "")
    add("ai", "AI suggestions", ai_on, "AI suggestions on." if ai_on else "AI suggestions off: no ANTHROPIC_API_KEY set. Everything else works.",
        "Set ANTHROPIC_API_KEY and restart the API.")
    add("proof", "Proof screen", data.get("answer_key") is not None and len(data.get("answer_key")) > 0,
        "Answer key loaded." if data.get("answer_key") is not None else "No answer key.", "Upload an answer key (line_id, true_part_id).")

    # currency
    missing_fx = []
    if have_spend and "currency" in spend:
        from .normalize import fx_lookup
        rate = fx_lookup(data.get("fx"), display_currency, fx_overrides)
        curs = sorted({str(c).upper().strip() for c in spend["currency"].dropna() if str(c).strip()})
        for c in curs:
            if rate(c) is None:
                missing_fx.append(c)
    # units
    unknown_units = []
    if have_spend and "purchase_uom" in spend:
        conv = list(rules.get("unit_conversions") or [])
        if data.get("conversions") is not None:
            conv += data["conversions"].to_dict("records")
        for u in sorted({str(x) for x in spend["purchase_uom"].dropna()}):
            ok = any(conversion_factor(u, b, conv) is not None for b in ("EA", "M", "KG", "L"))
            if not ok:
                unknown_units.append(u)
    currencies = sorted({str(c).upper() for c in spend["currency"].dropna()}) if have_spend and "currency" in spend else []
    blocking = []
    if not (have_bom and have_spend):
        blocking.append("Upload a BOM and a spend file.")
    if missing_fx:
        blocking.append(f"Enter exchange rates to {display_currency} for: {', '.join(missing_fx)}.")
    on = [f["label"] for f in feats if f["on"]]
    return {"features": feats, "missing_fx": missing_fx, "unknown_units": unknown_units, "currencies": currencies,
            "blocking": blocking, "can_run": not blocking,
            "sentence": (", ".join(on[:3]) + " on." if on else "Nothing is on yet.")}
