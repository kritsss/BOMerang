"""Run orchestration.

stage1  (expensive, cacheable): normalize, explode BOMs, group items, rungs 1-3, AI shortlist
stage2  (cheap): human decisions, price gate, quantity balance, unit inference, timing, statuses,
        allocation, ledger, BOM cost. Re-run after every review decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import bom as bomlib
from .checks import base_qty, coverage_check, infer_unit, price_gate, quantity_balance, timing_fit
from .items import build_items, prepare_lines
from .ladder import analyze_text, applicable_hard, build_parts, category_attrs, compare_attr, run_rungs
from .ledger import CLASS_LABEL, classify_and_allocate, ledger_summary
from .normalize import canon_unit, conversion_factor, fx_lookup, synonym_key
from .rules import hard_attributes_for

STATUS_LABEL = {"auto": "Auto-linked", "evidence": "Resolved by evidence", "review": "Needs review", "refused": "Refused",
                "nomatch": "No match", "human": "Linked by you", "notbom": "Not a BOM part"}
RUNG_LABEL = {"exact": "Exact ID", "xref": "Approved cross-reference", "learned": "Learned cross-reference", "spec": "Spec rules",
              "ai": "AI shortlist", "balance": "Quantity balance", "human": "Your review", "learned_notbom": "Learned rule"}


@dataclass
class Inputs:
    bom: pd.DataFrame
    spend: pd.DataFrame
    products: pd.DataFrame | None = None
    master: pd.DataFrame | None = None
    volumes: pd.DataFrame | None = None
    suppliers: pd.DataFrame | None = None
    conversions: pd.DataFrame | None = None
    fx: pd.DataFrame | None = None
    xrefs: pd.DataFrame | None = None
    attribute_columns: list[str] = field(default_factory=list)
    display_currency: str = "USD"
    fx_overrides: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)
    learned: list[dict] = field(default_factory=list)      # active learned rules
    decisions: list[dict] = field(default_factory=list)    # active review decisions


@dataclass
class Stage1:
    lines: pd.DataFrame
    items: pd.DataFrame
    parts: pd.DataFrame
    meta: dict
    results: list[dict]
    tree: pd.DataFrame
    leaves: pd.DataFrame
    products: pd.DataFrame
    req_pp: pd.DataFrame
    req_period: pd.DataFrame
    has_volumes: bool
    ai_used: bool
    ai_count: int = 0


def stage1(inp: Inputs, ai: Callable | None = None, progress: Callable[[str, float], None] | None = None) -> Stage1:
    pr = progress or (lambda *_: None)
    rules = inp.rules
    syn_key = synonym_key(rules.get("synonyms", []))
    pr("Normalizing spend lines", 0.05)
    rate = fx_lookup(inp.fx, inp.display_currency, inp.fx_overrides)
    lines = prepare_lines(inp.spend, rate, syn_key, rules)
    items = build_items(lines)
    pr("Exploding BOMs", 0.15)
    products = bomlib.top_level_products(inp.bom, inp.products)
    product_ids = products["product_id"].tolist()
    tree, leaves = bomlib.explode(inp.bom, product_ids)
    active = set(products.loc[products["status"] != "discontinued", "product_id"])
    has_volumes = inp.volumes is not None and len(inp.volumes) > 0
    req_pp, req_period = bomlib.required_quantities(leaves, inp.volumes, active)
    leaf_parts = set(leaves["part_id"].astype(str))
    pr("Building parts universe", 0.25)
    parts, meta = build_parts(inp.master, inp.bom, leaf_parts, inp.attribute_columns, syn_key, rules.get("synonyms", []))
    parts["in_active_bom"] = parts["part_id"].isin(set(leaves.loc[leaves["product_id"].isin(active), "part_id"]))
    pr("Matching: exact IDs, cross-references, spec rules", 0.35)
    xrefs = inp.xrefs
    results = run_rungs(items, parts, meta, rules, syn_key, xrefs, inp.learned)
    ai_count = 0
    if ai is not None:
        pr("AI shortlist", 0.7)
        ai_count = _ai_rung(items, parts, meta, results, rules, syn_key, ai)
    pr("Checks and allocation", 0.85)
    return Stage1(lines, items, parts, meta, results, tree, leaves, products, req_pp, req_period, has_volumes, ai is not None, ai_count)


def _ai_rung(items, parts, meta, results, rules, syn_key, ai) -> int:
    """AI only proposes. Every proposal is re-checked with the rules; a hard conflict drops it."""
    pidx = parts.set_index("part_id")
    cat_attrs = category_attrs(parts)
    n = 0
    order = items.sort_values("spend_cents", ascending=False).index
    for i in order:
        res = results[i]
        if res["pre_status"] not in ("ambiguous", "nomatch"):
            continue
        it = items.loc[i]
        cands = [c for c in res["candidates"] if c["verdict"] != "refused"][:8]
        if not cands:
            continue
        payload = {"description": it["description"], "supplier": it["supplier_name"], "supplier_part_no": it["supplier_pn"],
                   "candidates": [{"part_id": c["part_id"], "description": pidx.loc[c["part_id"], "description"],
                                   "attributes": {k: v for k, v in pidx.loc[c["part_id"], "attrs"].items() if v}} for c in cands],
                   "attribute_names": list(meta.keys())}
        out = ai(payload)
        if not out:
            continue
        n += 1
        best = out.get("best_part_id")
        ai_attrs = out.get("attributes") or {}
        if not best or best not in pidx.index:
            res["ai"] = {"note": out.get("reason") or "", "best": None, "rejected_by_rules": False, "attributes": ai_attrs}
            continue
        # re-check with the rules, with AI-read attributes filling only what the rules could not read
        an = analyze_text(f"{it['description']} {it['supplier_pn'] or ''}", syn_key)
        pr_ = pidx.loc[best]
        hard = applicable_hard(rules, meta, cat_attrs, pr_["category"])
        conflict = None
        attrs = []
        for a, am in meta.items():
            c = compare_attr(am, pr_["attrs"].get(a), an)
            c.update(attr=a, hard=a in hard, source="rules")
            if c["result"] == "missing" and ai_attrs.get(a) and pr_["attrs"].get(a):
                an2 = analyze_text(str(ai_attrs[a]), syn_key)
                c2 = compare_attr(am, pr_["attrs"].get(a), an2)
                if c2["result"] != "missing":
                    c = {**c2, "attr": a, "hard": a in hard, "source": "ai"}
            if c["hard"] and c["result"] == "differ":
                conflict = c
            attrs.append(c)
        res["ai"] = {"note": out.get("reason") or "", "best": best if conflict is None else None, "rejected_by_rules": conflict is not None,
                     "attributes": ai_attrs, "attrs": attrs}
        if conflict is None:
            opts = res.get("options") or []
            res["options"] = [best] + [o for o in opts if o != best]
            if res["pre_status"] == "nomatch":
                res["pre_status"] = "ambiguous"
                res["rung"] = "ai"
            res["ai_proposed"] = True
    return n


# ---------------------------------------------------------------------------

def _conversions(inp: Inputs) -> tuple[list[dict], dict[str, list[dict]]]:
    glob = list(inp.rules.get("unit_conversions") or [])
    if inp.conversions is not None and len(inp.conversions):
        glob += inp.conversions.to_dict("records")
    scoped: dict[str, list[dict]] = {}
    for lr in inp.learned:
        if lr["kind"] == "unit":
            v = lr["value"]
            if v.get("item_key"):
                scoped.setdefault(v["item_key"], []).append(v)
            else:
                glob.append(v)
    for d in inp.decisions:
        if d.get("action") == "approve" and d.get("unit_factor"):
            scoped.setdefault(d["item_key"], []).append({"purchase_uom": d.get("purchase_uom"), "base_uom": d.get("base_uom"), "factor": d["unit_factor"]})
    return glob, scoped


def stage2(s1: Stage1, inp: Inputs) -> dict[str, Any]:
    rules = inp.rules
    th = rules["thresholds"]
    band = rules["price_band"]
    items = s1.items
    parts = s1.parts
    pinfo = parts.set_index("part_id")
    glob_conv, scoped_conv = _conversions(inp)
    dec = {d["item_id"]: d for d in inp.decisions}
    req_tot = s1.req_pp.groupby("part_id")["required"].sum().to_dict() if len(s1.req_pp) else {}
    req_month = {}
    for r in s1.req_period.itertuples(index=False):
        req_month.setdefault(r.part_id, {})[str(r.period)[:7]] = float(r.required)
    rate = fx_lookup(inp.fx, inp.display_currency, inp.fx_overrides)

    qcache: dict[tuple[str, str], tuple] = {}
    I_id = items["item_id"].tolist()
    I_key = items["item_key"].tolist()
    I_qty = items["qty_by_uom"].tolist()
    I_ps = (items["prod_spend_cents"] / 100.0).tolist()
    I_ps_c = items["prod_spend_cents"].tolist()
    I_sp_c = items["spend_cents"].tolist()
    P_base = parts.set_index("part_id")["base_uom"].to_dict()
    P_set = set(P_base)

    def qty_for(i: int, p: str):
        key = (I_id[i], p)
        if key not in qcache:
            conv = scoped_conv.get(I_key[i], []) + glob_conv
            bu = P_base.get(p, "EA")
            qcache[key] = base_qty(I_qty[i], bu, conv)
        return qcache[key]

    def spend(i):
        return I_ps[i]

    def std_price(p):
        if p not in P_set:
            return None
        sc = pinfo.at[p, "standard_cost"]
        if sc is None or (isinstance(sc, float) and np.isnan(sc)):
            return None
        cur = pinfo.at[p, "std_currency"] if "std_currency" in pinfo.columns else None
        if cur and str(cur) not in ("nan", "None", ""):
            r = rate(cur)
            return float(sc) * r if r else None
        return float(sc)

    n = len(items)
    status = [None] * n
    part = [None] * n
    rung = [None] * n
    reason = [""] * n
    evidence: list[dict] = [{} for _ in range(n)]
    conf = [0.0] * n
    suggestion = [None] * n

    # 1) strong links and human decisions
    for i, res in enumerate(s1.results):
        iid = I_id[i]
        d = dec.get(iid)
        if d is not None:
            if d["action"] == "approve":
                status[i], part[i], rung[i] = "human", d["part_id"], "human"
                reason[i] = f"Approved by {d.get('who') or 'analyst'}" + (f": {d['reason']}" if d.get("reason") else "")
                if d.get("override_refusal"):
                    reason[i] += " (overrides a rule refusal)"
                conf[i] = 1.0
            else:
                status[i], rung[i] = "notbom", "human"
                reason[i] = f"Not a BOM part, per {d.get('who') or 'analyst'}" + (f": {d['reason']}" if d.get("reason") else "")
            continue
        ps = res["pre_status"]
        if ps == "linked":
            status[i], part[i], rung[i] = "auto", res["part_id"], res["rung"]
            x = res.get("xref") or {}
            if res["rung"] == "exact":
                reason[i], conf[i] = "Exact part ID on the purchase line.", 0.99
            elif res["rung"] == "xref":
                reason[i], conf[i] = f"Approved cross-reference{(' by ' + str(x.get('by'))) if x.get('by') else ''}.", 0.98
            else:
                reason[i], conf[i] = f"Learned rule from your review{(' (' + str(x.get('by')) + ')') if x.get('by') else ''}.", 0.97
        elif ps == "notbom":
            status[i], rung[i], reason[i] = "notbom", "learned_notbom", "; ".join(res["notes"])

    # unit check for strong links (an unknown unit always goes to review)
    for i in range(n):
        if status[i] in ("auto", "human") and part[i] is not None:
            q, unk = qty_for(i, part[i])
            if q is None and I_ps_c[i] != 0:
                if status[i] == "auto":
                    status[i], suggestion[i] = "review", part[i]
                    reason[i] = f"Unit unknown ({', '.join(u or '?' for u in unk)}): {reason[i]}"
                    part[i] = None

    # expected prices from strong links
    def acc(sel):
        agg: dict[str, list] = {}
        for i in sel:
            p = part[i]
            q, _ = qty_for(i, p)
            if q and q > 0:
                a = agg.setdefault(p, [0.0, 0.0, []])
                a[0] += spend(i)
                a[1] += q
                a[2].append(i)
        return agg

    strong = [i for i in range(n) if status[i] in ("auto", "human") and part[i] is not None]
    strong_agg = acc(strong)

    def expected(p, excl=None):
        a = strong_agg.get(p)
        if a:
            s, q = a[0], a[1]
            if excl is not None and excl in a[2]:
                qi, _ = qty_for(excl, p)
                s, q = s - spend(excl), q - (qi or 0)
            if q > 0:
                return s / q, "weighted average of certain links"
        sp = std_price(p)
        if sp:
            return sp, "standard cost"
        return None, None

    def price_check(i, p):
        q, _ = qty_for(i, p)
        pp = spend(i) / q if q and q > 0 and spend(i) else None
        e, src = expected(p, excl=i)
        g = price_gate(pp, e, band)
        g["expected_source"] = src
        return g

    # 2) spec links: price gate + unit
    for i, res in enumerate(s1.results):
        if status[i] is not None or res["pre_status"] != "spec_link":
            continue
        p = res["part_id"]
        q, unk = qty_for(i, p)
        g = price_check(i, p)
        evidence[i]["price"] = g
        if q is None and I_ps_c[i] != 0:
            status[i], suggestion[i], rung[i] = "review", p, "spec"
            reason[i] = f"Spec rules agree, but the unit is unknown ({', '.join(u or '?' for u in unk)})."
            conf[i] = 0.5
        elif g["result"] == "fail":
            status[i], suggestion[i], rung[i] = "review", p, "spec"
            reason[i] = "Spec rules agree, but the " + g["sentence"][0].lower() + g["sentence"][1:]
            conf[i] = 0.5
        else:
            status[i], part[i], rung[i] = "auto", p, "spec"
            hard = [c["attr"] for c in _cand(res, p)["attrs"] if c["hard"]] if _cand(res, p) else []
            reason[i] = "All hard attributes agree" + (f" ({', '.join(hard)})" if hard else "") + "."
            conf[i] = 0.85 + (0.05 if g["result"] == "pass" else 0.0)

    certain = [i for i in range(n) if status[i] in ("auto", "human") and part[i] is not None]
    fixed: dict[str, float] = {}
    for i in certain:
        q, _ = qty_for(i, part[i])
        if q:
            fixed[part[i]] = fixed.get(part[i], 0.0) + q
    months = sorted({m for m in s1.lines["month"].dropna()})
    item_month = {}
    if months:
        lp = s1.lines[~s1.lines["is_service"]]
        for (iid, m), q in lp.groupby(["item_id", "month"])["qty"].sum().items():
            item_month.setdefault(iid, {})[m] = float(q)
    timing_on = s1.has_volumes and len(months) >= 4 and any(len(v) >= 2 for v in req_month.values())

    # 3) ambiguous: quantity balance (+timing), unit inference
    for i, res in enumerate(s1.results):
        if status[i] is not None:
            continue
        ps = res["pre_status"]
        iid = I_id[i]
        if ps == "ambiguous":
            opts = [o for o in (res.get("options") or []) if o in P_set]
            qmap = {o: qty_for(i, o)[0] for o in opts}
            tcost, tfit, tser = {}, {}, {}
            if timing_on:
                for o in opts:
                    f = timing_fit(item_month.get(iid, {}), req_month.get(o, {}), months)
                    if f is not None:
                        tfit[o] = f["fit"]
                        tser[o] = f
                        tcost[o] = 0.1 * (1 - f["fit"])
            bal = None
            if s1.has_volumes and opts:
                bal = quantity_balance(opts, qmap, fixed, req_tot, float(th.get("balance_margin", 0.25)), tcost)
                evidence[i]["balance"] = bal
            if tfit:
                evidence[i]["timing"] = {"fit": tfit, "series": tser}
            unknown_unit = opts and all(qmap[o] is None for o in opts) and I_ps_c[i] != 0
            best = None
            if bal and bal.get("result") == "pass":
                best = bal["best"]
                g = price_check(i, best)
                evidence[i]["price"] = g
                if g["result"] != "fail":
                    status[i], part[i], rung[i] = "evidence", best, "balance"
                    reason[i] = f"Resolved by quantity balance (margin {bal['margin']:.2f} over the next option). " + bal["sentence"]
                    conf[i] = 0.70 + 0.2 * min(bal["margin"], 1.0)
                    if res.get("ai_proposed") and opts and opts[0] == best:
                        rung[i] = "ai+balance"
                    continue
            # review
            if bal and bal.get("best") and bal["best"] != "none":
                sug = bal["best"]
            else:
                sug = opts[0] if opts else None
            status[i], suggestion[i] = "review", sug
            rung[i] = "ai" if res.get("ai_proposed") and sug == (opts[0] if opts else None) else "spec"
            parts_txt = "; ".join(res.get("notes") or [])
            reason[i] = ("AI suggestion, rules re-checked: no hard conflict. " if rung[i] == "ai" else "") + (parts_txt or "More than one part fits.")
            if sug:
                evidence[i]["price"] = price_check(i, sug)
                if unknown_unit:
                    q_raw = sum(I_qty[i].values())
                    uom = next(iter(I_qty[i].keys()), None)
                    e, _ = expected(sug)
                    inf = infer_unit(q_raw, uom, P_base[sug], fixed.get(sug, 0.0), req_tot.get(sug, 0.0), spend(i), e)
                    if inf:
                        evidence[i]["unit"] = inf
                        reason[i] = "Unit unknown. " + inf["sentence"]
            ts = _cand(res, sug)["text_sim"] if sug and _cand(res, sug) else 0.3
            conf[i] = min(0.6, 0.3 + 0.3 * ts)
        elif ps == "refused":
            status[i], rung[i] = "refused", "spec"
            r0 = res["refused"][0] if res["refused"] else None
            if r0:
                diff = [c for c in r0["attrs"] if c["hard"] and c["result"] == "differ"]
                d0 = diff[0]
                reason[i] = f"Looks like {r0['part_id']}, but {d0['attr']} differs: {d0['why']}."
                suggestion[i] = r0["part_id"]
            else:
                reason[i] = "Refused by a hard attribute."
        else:
            status[i], rung[i] = "nomatch", None
            reason[i] = "; ".join(res.get("notes") or []) or "No part was similar enough."

    # unit-unknown links: suggest a factor
    for i in range(n):
        if status[i] == "review" and suggestion[i] and "unit" not in evidence[i] and ("Unit unknown" in reason[i] or "unit is unknown" in reason[i]):
            sug = suggestion[i]
            q_raw = sum(I_qty[i].values())
            conv = scoped_conv.get(I_key[i], []) + glob_conv
            uom = next((u for u in I_qty[i].keys() if conversion_factor(u or None, P_base[sug], conv) is None), None)
            e, _ = expected(sug)
            inf = infer_unit(q_raw, uom, P_base[sug], fixed.get(sug, 0.0), req_tot.get(sug, 0.0), spend(i), e)
            if inf:
                evidence[i]["unit"] = inf
                reason[i] = reason[i].rstrip(".") + ". " + inf["sentence"]

    # evidence for linked items: price + coverage
    for i in range(n):
        p = part[i] or suggestion[i]
        if p is None or p not in P_set:
            continue
        if "price" not in evidence[i]:
            evidence[i]["price"] = price_check(i, p)
        if s1.has_volumes and "balance" not in evidence[i]:
            q, _ = qty_for(i, p)
            fw = fixed.get(p, 0.0) - (q or 0.0 if part[i] == p and status[i] in ("auto", "human") else 0.0)
            evidence[i]["coverage"] = coverage_check(fw, q, req_tot.get(p, 0.0))
        if status[i] == "auto" and rung[i] == "spec" and evidence[i].get("coverage", {}).get("result") == "pass":
            conf[i] = min(0.95, conf[i] + 0.05)
        if timing_on and "timing" not in evidence[i]:
            f = timing_fit(item_month.get(I_id[i], {}), req_month.get(p, {}), months)
            if f is not None:
                evidence[i]["timing"] = {"fit": {p: f["fit"]}, "series": {p: f}}

    # assemble item table
    floor = float(th.get("review_money_floor", 0.3))
    out = items[["item_id", "item_key", "supplier_key", "supplier_name", "supplier_pn", "description", "norm_desc", "n_lines",
                 "spend_cents", "prod_spend_cents", "purchase_uom", "material_id_if_known"]].copy()
    out["status"] = status
    out["status_label"] = [STATUS_LABEL[s] for s in status]
    out["part_id"] = part
    out["suggestion_part_id"] = suggestion
    out["rung"] = rung
    out["rung_label"] = [RUNG_LABEL.get(r, r or "") if r else "" for r in rung]
    out["reason"] = [r if not r or r.endswith(".") else r + "." for r in reason]
    out["confidence"] = conf
    stake = []
    for i in range(n):
        sp = abs(I_sp_c[i])
        if status[i] == "review":
            stake.append(int(round(sp * max(1 - conf[i], floor))))
        else:
            stake.append(0)
    out["money_at_stake_cents"] = stake
    bq, ppb = [], []
    for i in range(n):
        p = part[i] or suggestion[i]
        if p and p in pinfo.index:
            q, _ = qty_for(i, p)
            bq.append(q)
            ppb.append(spend(i) / q if q else None)
        else:
            bq.append(None)
            ppb.append(None)
    out["base_qty"] = bq
    out["price_per_base"] = ppb
    out["ai_note"] = [(res.get("ai") or {}).get("note") if res.get("ai") else None for res in s1.results]
    out["ai_proposed"] = [bool(res.get("ai_proposed")) for res in s1.results]
    # evidence json-able
    ev_full = []
    for i, res in enumerate(s1.results):
        top = res["candidates"][:6] if status[i] in ("review", "refused", "nomatch") else res["candidates"][:3]
        p = part[i] or suggestion[i]
        if p and not any(c["part_id"] == p for c in top):
            c = _cand(res, p)
            if c:
                top = [c] + top[:5]
        ev_full.append({**evidence[i], "candidates": [_slim(c) for c in top], "refused": [_slim(c) for c in res["refused"][:5]],
                        "notes": res.get("notes") or [], "ai": res.get("ai")})
    out["evidence"] = ev_full

    # line-level base qty for allocation (only for linked items)
    lines = s1.lines.copy()
    st_map = out.set_index("item_id")
    base_line = pd.Series(np.nan, index=lines.index)
    lst = lines["item_id"].map(st_map["status"])
    linked_mask = lst.isin(["auto", "evidence", "human"])
    if linked_mask.any():
        sub = lines.loc[linked_mask, ["item_id", "purchase_uom_c", "qty"]].copy()
        sub["part_id"] = sub["item_id"].map(st_map["part_id"])
        sub["item_key"] = sub["item_id"].map(st_map["item_key"])
        fcache: dict = {}
        facs = []
        for u, p, ik in zip(sub["purchase_uom_c"], sub["part_id"], sub["item_key"]):
            sc = scoped_conv.get(ik)
            k = (u, p, ik if sc else None)
            if k not in fcache:
                fcache[k] = conversion_factor(u or None, P_base.get(p, "EA"), (sc or []) + glob_conv) if p in P_set else None
            facs.append(fcache[k])
        f = pd.Series(facs, index=sub.index, dtype="float64")
        base_line.loc[sub.index] = sub["qty"].astype(float) * f
    active_bom = set(parts.loc[parts["in_active_bom"], "part_id"])
    ledger, part_alloc = classify_and_allocate(lines, out[["item_id", "status", "part_id"]], parts, active_bom, s1.req_pp,
                                               s1.has_volumes, rules, base_line)
    total_cents = int(lines["cents"].sum())
    summ = ledger_summary(ledger, total_cents, s1.has_volumes)
    lines["status"] = lines["item_id"].map(st_map["status"])
    lines["part_id"] = lines["item_id"].map(st_map["part_id"])
    lines["base_qty"] = base_line
    main_cls = ledger.sort_values("cents", ascending=False).drop_duplicates("line_id").set_index("line_id")["class"]
    lines["class"] = lines["line_id"].map(main_cls)

    ladder = {
        "exact": int(((out["rung"] == "exact") & (out["status"] == "auto")).sum()),
        "xref": int(((out["rung"].isin(["xref", "learned"])) & (out["status"] == "auto")).sum()),
        "spec": int(((out["rung"] == "spec") & (out["status"] == "auto")).sum()),
        "ai": int(out["ai_proposed"].sum()),
        "evidence": int((out["status"] == "evidence").sum()),
        "review": int((out["status"] == "review").sum()),
        "human": int((out["status"].isin(["human"])).sum()),
        "refused": int((out["status"] == "refused").sum()),
        "nomatch": int((out["status"].isin(["nomatch", "notbom"])).sum()),
        "items": int(n),
        "auto_total": int(out["status"].isin(["auto", "evidence"]).sum()),
    }
    return {"items": out, "lines": lines, "ledger": ledger, "part_alloc": part_alloc, "summary": summ, "ladder": ladder,
            "timing_on": timing_on, "months": months}


def _cand(res: dict, p: str | None) -> dict | None:
    if p is None:
        return None
    for c in res["candidates"]:
        if c["part_id"] == p:
            return c
    return None


def _slim(c: dict) -> dict:
    return {"part_id": c["part_id"], "text_sim": c["text_sim"], "verdict": c["verdict"], "type_ok": c["type_ok"],
            "attrs": [{k: a.get(k) for k in ("attr", "hard", "result", "item_val", "part_val", "why", "source")} for a in c["attrs"]]}
