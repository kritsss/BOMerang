"""Independent checks: price gate, quantity balance, unit inference, timing fit. Deterministic."""
from __future__ import annotations

import numpy as np

from .normalize import canon_unit, conversion_factor
from .rules import UNIT_INFERENCE_FACTORS


def base_qty(qty_by_uom: dict[str, float], base_uom: str, conversions: list[dict]) -> tuple[float | None, list[str]]:
    """Convert an item's production quantity (by purchase unit) into the part's base unit.

    Returns (qty, unknown_units). qty is None if any unit cannot be converted (never guessed).
    """
    total, unknown = 0.0, []
    for u, q in qty_by_uom.items():
        f = conversion_factor(u or None, base_uom, conversions)
        if f is None:
            unknown.append(u)
        else:
            total += q * f
    if unknown:
        return None, unknown
    return total, []


def price_gate(price_per_base: float | None, expected: float | None, band: dict) -> dict:
    if price_per_base is None or expected is None or expected <= 0:
        return {"result": "not_decisive", "ratio": None, "price": price_per_base, "expected": expected,
                "low": band["low"], "high": band["high"], "sentence": "No expected price to compare with."}
    ratio = price_per_base / expected
    ok = band["low"] <= ratio <= band["high"]
    return {"result": "pass" if ok else "fail", "ratio": ratio, "price": price_per_base, "expected": expected,
            "low": band["low"], "high": band["high"],
            "sentence": (f"Price is {ratio:.2f}x the expected price, inside the band {band['low']:g}x to {band['high']:g}x." if ok
                         else f"Price outside expected range: {ratio:.2f}x the expected price (band {band['low']:g}x to {band['high']:g}x).")}


def _dev(fixed: float, add: float, req: float) -> float:
    denom = req if req > 0 else max(add, 1.0)
    return abs(fixed + add - req) / denom


def quantity_balance(options: list[str], qty_for: dict[str, float | None], fixed: dict[str, float], required: dict[str, float],
                     margin_needed: float, timing_cost: dict[str, float] | None = None) -> dict:
    """Per-item balance. For every option (each candidate part or 'none') sum the deviation
    |fixed + this item - required| / required over the affected parts. Best option wins with a margin."""
    affected = [p for p in options if qty_for.get(p) is not None]
    if not affected:
        return {"result": "not_decisive", "sentence": "Quantities cannot be compared (unknown unit).", "options": []}
    rows = []
    for opt in affected + ["none"]:
        dev = 0.0
        for p in affected:
            add = qty_for[p] if opt == p else 0.0
            dev += _dev(fixed.get(p, 0.0), add, required.get(p, 0.0))
        if timing_cost and opt in timing_cost:
            dev += timing_cost[opt]
        rows.append({"option": opt, "deviation": dev})
    rows.sort(key=lambda r: r["deviation"])
    best, second = rows[0], rows[1] if len(rows) > 1 else None
    margin = (second["deviation"] - best["deviation"]) if second else float("inf")
    cov = {}
    for p in affected:
        req = required.get(p, 0.0)
        cov[p] = {"fixed": fixed.get(p, 0.0), "item": qty_for[p], "required": req,
                  "coverage_if_linked": (fixed.get(p, 0.0) + qty_for[p]) / req if req > 0 else None,
                  "coverage_without": fixed.get(p, 0.0) / req if req > 0 else None}
    decisive = margin >= margin_needed and best["option"] != "none"
    sent = _balance_sentence(best["option"], affected, cov)
    return {"result": "pass" if decisive else "not_decisive", "best": best["option"], "margin": margin,
            "options": rows, "coverage": cov, "sentence": sent}


def _balance_sentence(best: str, affected: list[str], cov: dict) -> str:
    def pct(p):
        c = cov[p]["coverage_if_linked"]
        return "no recorded demand" if c is None else f"{c*100:.0f}%"
    order = sorted(affected, key=lambda x: (x != best, x))
    if not order:
        return ""
    first = order[0]
    s = f"Linking to {first} makes bought vs needed {pct(first)}"
    for p in order[1:]:
        s += f"; linking to {p} instead would make it {pct(p)}"
    return s + "."


def coverage_check(fixed_without: float, item_qty: float | None, required: float) -> dict:
    """Evidence for an already-linked item: does linking it keep bought close to needed?"""
    if item_qty is None or required <= 0:
        return {"result": "not_decisive", "coverage_if_linked": None,
                "sentence": "No production demand recorded for this part." if required <= 0 else "Unit unknown."}
    c = (fixed_without + item_qty) / required
    return {"result": "pass" if 0.75 <= c <= 1.33 else "not_decisive", "coverage_if_linked": c, "required": required,
            "fixed": fixed_without, "item": item_qty,
            "sentence": f"With this item, bought vs needed for the part is {c*100:.0f}%."}


def infer_unit(raw_qty: float, uom: str, base_uom: str, fixed: float, required: float, spend: float,
               expected_price: float | None) -> dict | None:
    """Suggest a factor for an unknown unit: by quantity balance if demand exists, else by price."""
    if raw_qty is None or raw_qty <= 0:
        return None
    scored = []
    for f in UNIT_INFERENCE_FACTORS:
        q = raw_qty * f
        if required > 0:
            score = abs(fixed + q - required) / required
            how = "balance"
        elif expected_price:
            score = abs(np.log((spend / q) / expected_price))
            how = "price"
        else:
            return None
        scored.append((score, f, how))
    scored.sort()
    score, f, how = scored[0]
    second = scored[1][0] if len(scored) > 1 else None
    bu = canon_unit(base_uom) or "EA"
    u = canon_unit(uom) or uom
    if how == "balance":
        sentence = f"The quantities add up only if 1 {u} = {f:g} {bu}."
    else:
        sentence = f"The price is plausible only if 1 {u} = {f:g} {bu}."
    return {"factor": f, "purchase_uom": u, "base_uom": bu, "how": how, "score": score, "second": second, "sentence": sentence}


def timing_fit(item_monthly: dict[str, float], demand_monthly: dict[str, float], months: list[str]) -> dict | None:
    """1 - 1/2 sum|purchase share - demand share| over 4 equal chunks; purchases shifted one month forward."""
    if len(months) < 4 or not item_monthly or not demand_monthly:
        return None
    pos = {m: i for i, m in enumerate(months)}
    n = len(months)
    chunk = lambda i: min(3, int(i * 4 / n))
    pur = np.zeros(4)
    dem = np.zeros(4)
    for m, q in item_monthly.items():
        if m in pos:
            pur[chunk(min(pos[m] + 1, n - 1))] += q
    for m, q in demand_monthly.items():
        if m in pos:
            dem[chunk(pos[m])] += q
    if pur.sum() <= 0 or dem.sum() <= 0:
        return None
    ps, ds = pur / pur.sum(), dem / dem.sum()
    labels = []
    for c in range(4):
        ms = [m for i, m in enumerate(months) if chunk(i) == c]
        labels.append(f"{ms[0]}–{ms[-1]}" if len(ms) > 1 else (ms[0] if ms else ""))
    return {"fit": float(1 - 0.5 * np.abs(ps - ds).sum()), "purchase": ps.tolist(), "demand": ds.tolist(), "chunks": labels}
