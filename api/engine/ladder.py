"""Parts universe, attribute comparison and the deterministic matching rungs 1-3.

Rung 1  exact ID          material_id_if_known equals a part id
Rung 2  cross-reference   (supplier, supplier part no) in approved or learned cross-references
Rung 3  spec rules        extracted attributes vs material master; hard conflicts are refused
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from .normalize import (basic_clean, dims_equal, extract_dims, extract_numbers, normalize_text,
                        parse_dim_value, parse_number_value, tokens, approx_equal, _DIM_RE)
from .rules import hard_attributes_for

STOP = {"for", "with", "and", "the", "mit", "und", "fuer", "fur", "von", "der", "die", "das", "of", "de", "la", "le", "et",
        "pc", "pcs", "ea", "mm", "cm", "in", "set", "type", "typ", "new", "part", "item", "nr", "no"}


def _pn(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = re.sub(r"[^a-z0-9]", "", str(v).lower())
    return s or None


@dataclass
class AttrMeta:
    name: str
    kind: str                       # dim | number | text
    vocab: set = field(default_factory=set)
    known_numbers: list = field(default_factory=list)
    known_dims: list = field(default_factory=list)


@dataclass
class Analyzed:
    text: str                        # normalized text with dimensions masked out
    tokens: set
    dims: list
    numbers: list


def analyze_text(raw: str, syn_key) -> Analyzed:
    """Clean, pull out dimensions first (so their numbers are not read as grades), then apply synonyms."""
    t = basic_clean(raw)
    dims = extract_dims(t)
    numbers = extract_numbers(t)
    masked = _DIM_RE.sub(" ", t)
    norm = normalize_text(masked, syn_key)
    return Analyzed(norm, tokens(norm), dims, numbers)


def _group_matches(group: str, col: str, syn_key) -> bool:
    g = basic_clean(group)
    c = normalize_text(col, syn_key)
    return bool(g) and (g == c or g in c.split() or g in c)


def build_parts(master: pd.DataFrame | None, bom: pd.DataFrame, leaf_parts: set[str], attribute_columns: list[str],
                syn_key, synonyms: list[dict]) -> tuple[pd.DataFrame, dict[str, AttrMeta]]:
    """Universe of linkable parts = material master parts + BOM leaf components."""
    recs: dict[str, dict] = {}
    if master is not None and len(master):
        m = master.copy()
        m["part_id"] = m["part_id"].astype(str)
        for r in m.to_dict("records"):
            recs[r["part_id"]] = r
    bdesc = {}
    if "description_as_written" in bom:
        for c, d in zip(bom["component_id"].astype(str), bom["description_as_written"]):
            if d is not None and str(d) not in ("", "nan", "None") and c not in bdesc:
                bdesc[c] = str(d)
    buom = {}
    if "uom" in bom:
        for c, u in zip(bom["component_id"].astype(str), bom["uom"]):
            if u is not None and str(u) not in ("", "nan", "None") and c not in buom:
                buom[c] = str(u)
    for p in leaf_parts:
        if p not in recs:
            recs[p] = {"part_id": p}
    rows = []
    for pid, r in recs.items():
        desc = r.get("description")
        if desc is None or str(desc) in ("", "nan", "None"):
            desc = bdesc.get(pid, "")
        base = r.get("base_uom")
        if base is None or str(base) in ("", "nan", "None"):
            base = buom.get(pid, "EA")
        sc = pd.to_numeric(pd.Series([r.get("standard_cost")]), errors="coerce").iloc[0]
        cat = r.get("category")
        cat = None if cat is None or str(cat) in ("", "nan", "None") else str(cat)
        attrs = {}
        for a in attribute_columns:
            v = r.get(a)
            if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in ("", "nan", "None"):
                attrs[a] = None
            else:
                attrs[a] = str(v).strip()
        bom_desc = bdesc.get(pid)
        rows.append({"part_id": pid, "description": str(desc or ""), "bom_description": bom_desc, "category": cat,
                     "base_uom": str(base), "standard_cost": None if pd.isna(sc) else float(sc), "attrs": attrs,
                     "in_bom": pid in leaf_parts, "in_master": pid in (set(master["part_id"].astype(str)) if master is not None and len(master) else set()),
                     "std_currency": r.get("currency")})
    parts = pd.DataFrame(rows)
    if parts.empty:
        parts = pd.DataFrame(columns=["part_id", "description", "bom_description", "category", "base_uom", "standard_cost", "attrs", "in_bom", "in_master", "std_currency"])

    # attribute metadata (kind + vocabulary) learned from the master itself
    meta: dict[str, AttrMeta] = {}
    for a in attribute_columns:
        vals = [r[a] for r in parts["attrs"] if r.get(a)]
        if not vals:
            meta[a] = AttrMeta(a, "text")
            continue
        n_dim = sum(1 for v in vals if parse_dim_value(v))
        n_num = sum(1 for v in vals if parse_number_value(v) is not None)
        if n_dim >= 0.6 * len(vals):
            kind = "dim"
        elif n_num >= 0.8 * len(vals):
            kind = "number"
        else:
            kind = "text"
        am = AttrMeta(a, kind)
        if kind == "dim":
            am.known_dims = list({parse_dim_value(v) for v in vals if parse_dim_value(v)})
        elif kind == "number":
            am.known_numbers = sorted({parse_number_value(v) for v in vals if parse_number_value(v) is not None})
        else:
            voc = set()
            for v in vals:
                voc |= {t for t in tokens(normalize_text(v, syn_key)) if t not in STOP}
            for s in synonyms:
                if s.get("group") and _group_matches(str(s["group"]), a, syn_key):
                    voc |= {t for t in tokens(basic_clean(s.get("canonical", ""))) if t not in STOP}
            am.vocab = voc
        meta[a] = am

    all_vocab = set().union(*[m.vocab for m in meta.values()]) if meta else set()
    texts, type_toks, analyzed = [], [], []
    for r in parts.itertuples(index=False):
        attr_text = " ".join(f"{v}" for v in r.attrs.values() if v)
        full = f"{r.description} {r.bom_description or ''} {attr_text}"
        an = analyze_text(full, syn_key)
        analyzed.append(an)
        texts.append(normalize_text(full, syn_key))
        dt = analyze_text(f"{r.description} {r.bom_description or ''}", syn_key)
        tt = {t for t in dt.tokens if len(t) >= 3 and not re.search(r"\d", t) and t not in STOP and t not in all_vocab}
        type_toks.append(tt)
    parts["match_text"] = texts
    parts["type_tokens"] = type_toks
    parts["norm_desc"] = [normalize_text(d, syn_key) for d in parts["description"]]
    return parts.reset_index(drop=True), meta


# ---------------------------------------------------------------------------
# Attribute comparison

def compare_attr(meta: AttrMeta, part_val, item: Analyzed) -> dict:
    """Return {result: agree|differ|missing, item_val, part_val, why}."""
    if part_val is None:
        return {"result": "missing", "item_val": None, "part_val": None, "why": "not stated in the material master"}
    if meta.kind == "dim":
        pv = parse_dim_value(part_val)
        if pv is None:
            return {"result": "missing", "item_val": None, "part_val": part_val, "why": "master value not readable"}
        same_len = [d for d in item.dims if len(d) == len(pv)]
        if any(dims_equal(pv, d) for d in same_len):
            d = next(d for d in same_len if dims_equal(pv, d))
            return {"result": "agree", "item_val": _fmt_dim(d), "part_val": part_val, "why": ""}
        if same_len:
            return {"result": "differ", "item_val": _fmt_dim(same_len[0]), "part_val": part_val, "why": "different size"}
        return {"result": "missing", "item_val": None, "part_val": part_val, "why": "size not stated on the invoice"}
    if meta.kind == "number":
        pv = parse_number_value(part_val)
        if pv is None:
            return {"result": "missing", "item_val": None, "part_val": part_val, "why": "master value not readable"}
        found = [k for k in meta.known_numbers if any(approx_equal(k, x, 0.005) for x in item.numbers)]
        if any(approx_equal(pv, k, 0.005) for k in found):
            return {"result": "agree", "item_val": _fmt_num(pv), "part_val": part_val, "why": ""}
        if found:
            return {"result": "differ", "item_val": ", ".join(_fmt_num(k) for k in found), "part_val": part_val, "why": "different value"}
        return {"result": "missing", "item_val": None, "part_val": part_val, "why": "not stated on the invoice"}
    # text
    part_terms = {t for t in tokens(part_val_norm(part_val, meta)) if t in meta.vocab}
    item_terms = item.tokens & meta.vocab
    if not part_terms:
        return {"result": "missing", "item_val": " ".join(sorted(item_terms)) or None, "part_val": part_val, "why": "master value not recognised"}
    if not item_terms:
        return {"result": "missing", "item_val": None, "part_val": part_val, "why": "not stated on the invoice"}
    extra_item, extra_part = item_terms - part_terms, part_terms - item_terms
    if extra_item and extra_part:
        return {"result": "differ", "item_val": " ".join(sorted(item_terms)), "part_val": part_val,
                "why": f"invoice says {' '.join(sorted(extra_item))}, part is {' '.join(sorted(extra_part))}"}
    return {"result": "agree", "item_val": " ".join(sorted(item_terms)), "part_val": part_val, "why": ""}


_PV_CACHE: dict = {}


def part_val_norm(v: str, meta: AttrMeta) -> str:
    key = (v, id(meta))
    if key not in _PV_CACHE:
        _PV_CACHE[key] = normalize_text(v, _CURRENT_SYN[0])
    return _PV_CACHE[key]


_CURRENT_SYN: list = [tuple()]


def _fmt_dim(d) -> str:
    return "x".join(_fmt_num(x) for x in d)


def _fmt_num(x: float) -> str:
    return f"{x:g}"


def category_attrs(parts: pd.DataFrame) -> dict:
    """Attributes the master actually fills, per category. A hard attribute only applies where it is filled."""
    out: dict = {}
    for cat, attrs in zip(parts["category"], parts["attrs"]):
        s = out.setdefault(cat, set())
        s |= {a for a, v in attrs.items() if v}
    return out


def applicable_hard(rules: dict, meta: dict, cat_attrs: dict, category) -> list[str]:
    filled = cat_attrs.get(category, set())
    return [a for a in hard_attributes_for(rules, category) if a in meta and a in filled]


def type_ok(item: Analyzed, part_type_tokens: set) -> bool:
    if not part_type_tokens:
        return True
    if item.tokens & part_type_tokens:
        return True
    for a in item.tokens:
        if len(a) < 4:
            continue
        for b in part_type_tokens:
            if fuzz.ratio(a, b) >= 88:
                return True
    return False


# ---------------------------------------------------------------------------
# Text similarity (TF-IDF char n-grams; optional multilingual embeddings)

def text_similarity_topk(item_texts: list[str], part_texts: list[str], k: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (indices [n_items, k], scores [n_items, k]) of the top-k parts per item."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    n_i, n_p = len(item_texts), len(part_texts)
    k = max(1, min(k, n_p))
    if n_i == 0 or n_p == 0:
        return np.zeros((n_i, 0), dtype=int), np.zeros((n_i, 0))
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True, min_df=1)
    vec.fit(list(part_texts) + list(item_texts))
    P = vec.transform(part_texts)
    I = vec.transform(item_texts)
    emb_I = emb_P = None
    if os.environ.get("BOMERANG_EMBEDDINGS", "0") == "1":
        try:  # optional, heavy dependency
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(os.environ.get("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"))
            emb_P = model.encode(part_texts, normalize_embeddings=True)
            emb_I = model.encode(item_texts, normalize_embeddings=True)
        except Exception:
            emb_I = emb_P = None
    idx = np.zeros((n_i, k), dtype=int)
    sc = np.zeros((n_i, k))
    chunk = max(1, 2_000_000 // max(n_p, 1))
    PT = P.T.tocsc()
    for s in range(0, n_i, chunk):
        e = min(n_i, s + chunk)
        S = (I[s:e] @ PT).toarray()
        if emb_I is not None:
            S = 0.5 * S + 0.5 * np.clip(emb_I[s:e] @ emb_P.T, 0, 1)
        if k < n_p:
            part = np.argpartition(-S, k - 1, axis=1)[:, :k]
        else:
            part = np.tile(np.arange(n_p), (e - s, 1))
        ps = np.take_along_axis(S, part, axis=1)
        order = np.argsort(-ps, axis=1)
        idx[s:e] = np.take_along_axis(part, order, axis=1)
        sc[s:e] = np.take_along_axis(ps, order, axis=1)
    return idx, sc


def text_sim_pair(a: str, b: str) -> float:
    from sklearn.feature_extraction.text import TfidfVectorizer
    if not a or not b:
        return 0.0
    v = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit([a, b])
    X = v.transform([a, b])
    return float((X[0] @ X[1].T).toarray()[0, 0])


# ---------------------------------------------------------------------------
# Rungs 1-3

def run_rungs(items: pd.DataFrame, parts: pd.DataFrame, meta: dict[str, AttrMeta], rules: dict, syn_key,
              xrefs: pd.DataFrame | None, learned: list[dict]) -> list[dict]:
    """Deterministic rungs. Returns one result dict per item (same order as `items`)."""
    _CURRENT_SYN[0] = syn_key
    _PV_CACHE.clear()
    th = rules["thresholds"]
    k = int(th.get("candidate_top_k", 12))
    min_sim = float(th.get("min_similarity", 0.2))
    auto_min = float(th.get("auto_link_min_text", 0.3))
    part_ids = parts["part_id"].tolist()
    part_index = {p: i for i, p in enumerate(part_ids)}
    pnorm = {p.lower(): p for p in part_ids}

    # cross references: approved file + learned
    xmap: dict[tuple[str, str], dict] = {}
    if xrefs is not None and len(xrefs):
        for r in xrefs.to_dict("records"):
            sk = basic_clean(r.get("supplier_id") or r.get("supplier_name") or "")
            pn = _pn(r.get("supplier_part_no"))
            if pn and str(r.get("part_id")) in part_index:
                xmap[(sk, pn)] = {"part_id": str(r["part_id"]), "source": "approved", "by": r.get("approved_by"), "on": str(r.get("approved_on") or "")}
    lx_item: dict[str, dict] = {}
    notbom: dict[str, dict] = {}
    for lr in learned:
        if lr["kind"] == "xref":
            v = lr["value"]
            if v.get("supplier_pn"):
                xmap[(v["supplier_key"], _pn(v["supplier_pn"]))] = {"part_id": v["part_id"], "source": "learned", "by": lr.get("who"), "on": lr.get("created_at"), "rule_id": lr.get("id")}
            lx_item[v["item_key"]] = {"part_id": v["part_id"], "source": "learned", "by": lr.get("who"), "on": lr.get("created_at"), "rule_id": lr.get("id")}
        elif lr["kind"] == "notbom":
            notbom[lr["value"]["item_key"]] = lr

    item_an = [analyze_text(f"{d} {pn or ''}", syn_key) for d, pn in zip(items["description"], items["supplier_pn"])]
    idx, sc = text_similarity_topk(items["norm_desc"].tolist(), parts["match_text"].tolist(), k)

    results = []
    parts_recs = parts.to_dict("records")
    cat_attrs = category_attrs(parts)
    for i, it in enumerate(items.itertuples(index=False)):
        res = {"item_id": it.item_id, "rung": None, "pre_status": None, "part_id": None, "candidates": [], "refused": [], "notes": []}
        # rung 1 exact id
        mid = it.material_id_if_known
        if mid and str(mid).lower() in pnorm:
            res.update(rung="exact", pre_status="linked", part_id=pnorm[str(mid).lower()])
        # rung 2 cross reference
        if res["part_id"] is None:
            pn = _pn(it.supplier_pn)
            hit = xmap.get((it.supplier_key, pn)) if pn else None
            if hit is None:
                hit = lx_item.get(it.item_key)
            if hit is not None:
                res.update(rung="xref" if hit["source"] == "approved" else "learned", pre_status="linked", part_id=hit["part_id"], xref=hit)
            elif it.item_key in notbom:
                lr = notbom[it.item_key]
                res.update(rung="learned_notbom", pre_status="notbom", notes=[f"Marked 'not a BOM part' by {lr.get('who') or 'analyst'}: {lr.get('why') or ''}"])
        an = item_an[i]
        # rung 3 spec rules (always computed, also as evidence for linked items)
        cands = []
        for j, s in zip(idx[i], sc[i]):
            if s < min_sim * 0.5:
                continue
            pr = parts_recs[j]
            hard = applicable_hard(rules, meta, cat_attrs, pr["category"])
            attrs = []
            for a, am in meta.items():
                c = compare_attr(am, pr["attrs"].get(a), an)
                c.update(attr=a, hard=a in hard, source="rules")
                attrs.append(c)
            hard_res = [c["result"] for c in attrs if c["hard"]]
            tok = type_ok(an, pr["type_tokens"])
            if "differ" in hard_res:
                verdict = "refused"
            elif hard_res and all(r == "agree" for r in hard_res) and tok:
                verdict = "full"
            else:
                verdict = "partial"
            soft_agree = sum(1 for c in attrs if not c["hard"] and c["result"] == "agree")
            soft_diff = sum(1 for c in attrs if not c["hard"] and c["result"] == "differ")
            score = float(s) + 0.05 * soft_agree - 0.1 * soft_diff + (0.05 if tok and pr["type_tokens"] else 0) - (0.1 if not tok else 0)
            cands.append({"part_id": pr["part_id"], "text_sim": round(float(s), 4), "score": round(score, 4), "verdict": verdict,
                          "type_ok": tok, "attrs": attrs, "hard_defined": bool(hard)})
        cands.sort(key=lambda c: -c["score"])
        res["candidates"] = cands
        res["refused"] = [c for c in cands if c["verdict"] == "refused" and c["text_sim"] >= min_sim]
        if res["pre_status"] is None:
            full = [c for c in cands if c["verdict"] == "full" and c["text_sim"] >= min_sim]
            partial = [c for c in cands if c["verdict"] == "partial" and c["text_sim"] >= min_sim]
            best_any = max([c["text_sim"] for c in cands], default=0.0)
            if len(full) == 1 and full[0]["text_sim"] >= auto_min:
                res.update(rung="spec", pre_status="spec_link", part_id=full[0]["part_id"])
            elif full:
                pool = full + [c for c in partial if c["score"] >= 0.75 * full[0]["score"]]
                res.update(rung="spec", pre_status="ambiguous", options=[c["part_id"] for c in pool[:5]])
                if len(full) > 1:
                    res["notes"].append(f"{len(full)} parts agree on every hard attribute")
                else:
                    res["notes"].append("Hard attributes agree but the description is not similar enough to link automatically")
            elif partial:
                best_p = partial[0]["score"]
                best_ref = max([c["text_sim"] for c in res["refused"]], default=0.0)
                if best_ref > 0 and partial[0]["text_sim"] < 0.6 * best_ref:
                    res.update(rung="spec", pre_status="refused", part_id=None)
                else:
                    pool = [c for c in partial if c["score"] >= 0.75 * best_p][:5]
                    res.update(rung="spec", pre_status="ambiguous", options=[c["part_id"] for c in pool])
                    miss = sorted({c["attr"] for c in pool[0]["attrs"] if c["hard"] and c["result"] == "missing"})
                    if miss:
                        res["notes"].append("Missing on invoice or master: " + ", ".join(miss))
                    elif not pool[0]["hard_defined"]:
                        res["notes"].append("No hard attributes set for this category: text similarity alone cannot link")
            elif res["refused"]:
                res.update(rung="spec", pre_status="refused")
            else:
                res.update(rung=None, pre_status="nomatch")
                if best_any > 0:
                    res["notes"].append("No part was similar enough")
        results.append(res)
    return results
