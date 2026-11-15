"""Guardrails for anything the LLM returns."""
from __future__ import annotations

import re

from engine.normalize import approx_equal, extract_numbers

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_supported(value: str, source: str, tol: float = 0.02) -> bool:
    """Every number in `value` must appear in `source` within 2% (mm <-> inch allowed)."""
    src = extract_numbers(source)
    for x in extract_numbers(str(value)):
        ok = any(approx_equal(x, s, tol) or approx_equal(x, s * 25.4, tol) or approx_equal(x, s / 25.4, tol) for s in src)
        if not ok:
            return False
    return True


def filter_attributes(attrs: dict, source: str, allowed: list[str]) -> dict:
    out = {}
    for k, v in (attrs or {}).items():
        if k not in allowed or v in (None, ""):
            continue
        if numbers_supported(str(v), source):
            out[k] = str(v)
    return out


def explanation_ok(text: str, allowed_numbers_source: str) -> bool:
    """Explanations may only restate numbers passed to them."""
    return numbers_supported(text, allowed_numbers_source, tol=0.005)
