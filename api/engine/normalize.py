"""Normalization: text, synonyms, spec extraction, units and currency.

Pure functions; no dataset-specific knowledge.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Iterable

import numpy as np
import pandas as pd

from .rules import UNIT_ALIASES, UNIT_FAMILIES

_NUM = r"\d+(?:[.,]\d+)?"
_DIM_RE = re.compile(rf"(?<![\w.])(?:m|ø|⌀|d|dia)?\s*({_NUM})\s*(?:mm|in|\")?\s*[x×*]\s*({_NUM})(?:\s*(?:mm|in|\")?\s*[x×*]\s*({_NUM}))?\s*(mm|in|\"|cm)?", re.I)
_DIA_RE = re.compile(rf"(?:ø|⌀|dia(?:meter)?\.?|diameter)\s*({_NUM})", re.I)
_THREAD_RE = re.compile(rf"\bm({_NUM})(?:\s*[x×]\s*({_NUM}))?\b", re.I)
_DASH_RE = re.compile(r"\b(\d)-(\d{3})\b")                 # O-ring dash sizes such as 2-214
_BEARING_RE = re.compile(r"\b(\d{4,5})(?:[-\s]?(2rs|2z|zz|rs|2rsh|c3))?\b", re.I)
_NUMBER_RE = re.compile(rf"(?<![\w.]){_NUM}(?![\w])|(?<=[a-z]){_NUM}|{_NUM}(?=[a-z])", re.I)
_PUNCT_RE = re.compile(r"[^\w\s.\-/x×\"]+", re.U)
_SPACE_RE = re.compile(r"\s+")


def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)) if s else s


@lru_cache(maxsize=64)
def _compile_synonyms(key: tuple[tuple[str, str], ...]) -> tuple[re.Pattern | None, dict[str, str]]:
    mapping = {}
    for term, canon in key:
        t = basic_clean(term)
        if t:
            mapping[t] = basic_clean(canon)
    if not mapping:
        return None, {}
    terms = sorted(mapping, key=len, reverse=True)
    pat = re.compile(r"(?<![\w.])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w])")
    return pat, mapping


def synonym_key(synonyms: Iterable[dict]) -> tuple[tuple[str, str], ...]:
    return tuple((str(s.get("term", "")), str(s.get("canonical", ""))) for s in synonyms if s.get("term"))


def basic_clean(s: str) -> str:
    if isinstance(s, str):
        return _basic_clean_cached(s)
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = str(s).lower().strip()
    s = s.replace("ß", "ss")
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = strip_accents(s)
    s = _PUNCT_RE.sub(" ", s)
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    return _SPACE_RE.sub(" ", s).strip()


@lru_cache(maxsize=500000)
def _basic_clean_cached(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = strip_accents(s)
    s = _PUNCT_RE.sub(" ", s)
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    return _SPACE_RE.sub(" ", s).strip()


@lru_cache(maxsize=500000)
def normalize_text(s: str, syn_key: tuple[tuple[str, str], ...]) -> str:
    """lowercase, transliterate, strip punctuation, apply the synonym table (single pass, longest first)."""
    t = basic_clean(s)
    pat, mapping = _compile_synonyms(syn_key)
    if pat is not None and t:
        t = pat.sub(lambda m: mapping.get(m.group(1), m.group(1)), t)
        # split glued words like "ss304" or "nbr90" (2+ letters then digits), then apply synonyms again
        t2 = _GLUED_RE.sub(lambda m: f"{m.group(1)} {m.group(2)}" if m.group(1) in mapping or m.group(1) in _CANON_WORDS(syn_key) else m.group(0), t)
        if t2 != t:
            t = pat.sub(lambda m: mapping.get(m.group(1), m.group(1)), t2)
    return _SPACE_RE.sub(" ", t).strip()


@lru_cache(maxsize=64)
def _CANON_WORDS(key) -> frozenset:
    return frozenset(w for _, c in key for w in basic_clean(c).split())


_GLUED_RE = re.compile(r"(?<![\w.])([a-z]{2,})(\d+(?:\.\d+)?)(?![\w])")


_CODE_RE = re.compile(r"^([a-z]{1,4})(\d{2,}(?:\.\d+)?)$")
_NUM_UNIT_RE = re.compile(r"^(\d+(?:\.\d+)?)([a-z]{1,3})$")


def tokens(s: str) -> set[str]:
    """Word tokens of an already-normalized string (dims split into their numbers)."""
    if not s:
        return set()
    out = set()
    for tok in re.split(r"[\s/]+", s):
        tok = tok.strip(".-\"").lstrip("ø⌀")
        if not tok or tok == "x":
            continue
        out.add(tok)
        if "-" in tok:
            out.update(p for p in tok.split("-") if p)
        m2 = _CODE_RE.match(tok)
        if m2:  # "cp200" -> cp, 200 ; "d120" -> d, 120 (codes; "ie3" stays whole)
            out.update((m2.group(1), m2.group(2)))
        m = _NUM_UNIT_RE.match(tok)
        if m:  # "16mm" -> 16, mm ; "3kw" -> 3, kw
            out.update((m.group(1), m.group(2)))
    return out


def extract_dims(text: str) -> list[tuple[float, ...]]:
    """All dimension tuples (a x b [x c]) in mm. Inch-marked tuples are converted to mm."""
    out: list[tuple[float, ...]] = []
    for m in _DIM_RE.finditer(text or ""):
        nums = [g for g in m.groups()[:3] if g]
        unit = (m.group(4) or "").lower()
        vals = tuple(_to_float(n) for n in nums)
        if unit in ("in", '"'):
            vals = tuple(round(v * 25.4, 3) for v in vals)
        elif unit == "cm":
            vals = tuple(v * 10 for v in vals)
        out.append(vals)
    return out


def extract_numbers(text: str) -> list[float]:
    out = []
    for m in re.finditer(_NUM, text or ""):
        try:
            out.append(_to_float(m.group(0)))
        except ValueError:
            pass
    return out


def extract_specs(text: str) -> dict:
    """Regex spec extraction on a normalized string."""
    t = text or ""
    dims = extract_dims(t)
    threads = []
    for m in _THREAD_RE.finditer(t):
        threads.append(f"m{m.group(1)}")
    dias = [_to_float(m.group(1)) for m in _DIA_RE.finditer(t)]
    dash = [f"{a}-{b}" for a, b in _DASH_RE.findall(t)]
    return {"dims": dims, "threads": threads, "diameters": dias, "dash_sizes": dash, "numbers": extract_numbers(t)}


@lru_cache(maxsize=200000)
def parse_dim_value(v: str) -> tuple[float, ...] | None:
    """Parse a master attribute value as a dimension tuple ("8x120", "20 x 2 mm", "M6x20")."""
    if v is None:
        return None
    s = basic_clean(str(v))
    d = extract_dims(s)
    if d:
        return d[0]
    return None


@lru_cache(maxsize=200000)
def parse_number_value(v) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = basic_clean(str(v))
    if not s:
        return None
    if extract_dims(s):
        return None
    nums = extract_numbers(s)
    letters = re.sub(r"[\d.\s]", "", s)
    # a single number with at most a short unit/suffix, e.g. "90", "90 shore", "12mm"
    if len(nums) == 1 and len(letters) <= 8:
        return nums[0]
    return None


def approx_equal(a: float, b: float, tol: float = 0.02) -> bool:
    if a == b:
        return True
    m = max(abs(a), abs(b))
    return m > 0 and abs(a - b) / m <= tol


def dims_equal(a: tuple[float, ...], b: tuple[float, ...], tol: float = 0.01) -> bool:
    if len(a) != len(b):
        return False
    sa, sb = sorted(a), sorted(b)
    if all(approx_equal(x, y, tol) for x, y in zip(sa, sb)):
        return True
    # one side in inches, the other in mm
    for f in (25.4, 1 / 25.4):
        if all(approx_equal(x * f, y, tol) for x, y in zip(sa, sb)):
            return True
    return False


# --- Units -----------------------------------------------------------------

def canon_unit(u) -> str | None:
    if u is None or (isinstance(u, float) and np.isnan(u)):
        return None
    s = str(u).strip()
    if not s:
        return None
    low = s.lower().replace(".", "").strip()
    if low in UNIT_ALIASES:
        return UNIT_ALIASES[low]
    return s.upper()


def unit_family(u: str | None) -> str | None:
    if u is None:
        return None
    for fam, units in UNIT_FAMILIES.items():
        if u in units:
            return fam
    return None


def conversion_factor(purchase_uom, base_uom, user_conversions: list[dict] | None = None) -> float | None:
    """Factor such that base_qty = purchase_qty * factor. None if unknown (never guessed)."""
    pu = canon_unit(purchase_uom)
    bu = canon_unit(base_uom) or "EA"
    if pu is None:
        pu = bu  # no unit given on the line: assume the base unit only if the column is empty
    # user / learned conversions win
    for c in user_conversions or []:
        cp, cb = canon_unit(c.get("purchase_uom")), canon_unit(c.get("base_uom"))
        if cp == pu and (cb == bu or not cb):
            try:
                return float(c.get("factor"))
            except (TypeError, ValueError):
                continue
    if pu == bu:
        return 1.0
    fb = unit_family(bu)
    # "M" is metre in the length family but "per thousand" for count units
    if pu == "M" and fb == "count":
        pu = "TH"
    fp = unit_family(pu)
    if fp and fp == fb:
        return UNIT_FAMILIES[fp][pu] / UNIT_FAMILIES[fb][bu]
    return None


# --- Currency ----------------------------------------------------------------

def fx_lookup(fx: pd.DataFrame | None, display: str, overrides: dict[str, float] | None = None):
    """Return function(currency, month) -> rate to display currency, or None."""
    overrides = {str(k).upper(): float(v) for k, v in (overrides or {}).items() if v not in (None, "")}
    table: dict[tuple[str, str | None], float] = {}
    if fx is not None and len(fx):
        for r in fx.itertuples(index=False):
            cur = str(getattr(r, "currency", "")).upper().strip()
            per = getattr(r, "period", None)
            per = str(per)[:7] if per is not None and str(per) not in ("", "nan", "None", "NaT") else None
            try:
                rate = float(getattr(r, "rate_to_display_currency"))
            except (TypeError, ValueError):
                continue
            table[(cur, per)] = rate
    disp = (display or "").upper()

    def rate(cur, month=None):
        c = str(cur or "").upper().strip() or disp
        if c == disp:
            return 1.0
        if month and (c, str(month)[:7]) in table:
            return table[(c, str(month)[:7])]
        if c in overrides:
            return overrides[c]
        if (c, None) in table:
            return table[(c, None)]
        per_vals = [v for (cc, p), v in table.items() if cc == c]
        if per_vals:
            return float(np.mean(per_vals))
        return None

    return rate
