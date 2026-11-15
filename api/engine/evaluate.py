"""Proof: compare matcher modes against an uploaded answer key. Shows only what the run produced."""
from __future__ import annotations

import copy

import pandas as pd

from .pipeline import Inputs, stage1, stage2

LINKED = ("auto", "evidence", "human")


def item_truth(lines: pd.DataFrame, key: pd.DataFrame) -> dict[str, dict]:
    k = key.copy()
    k["line_id"] = k["line_id"].astype(str)
    k["true_part_id"] = k["true_part_id"].astype(str).str.strip()
    m = lines[["line_id", "item_id"]].merge(k, on="line_id", how="inner")
    out = {}
    for iid, g in m.groupby("item_id"):
        t = g["true_part_id"].value_counts().index[0]
        cls = None
        if "class" in g and g["class"].notna().any():
            cls = str(g["class"].dropna().iloc[0])
        out[iid] = {"truth": None if t.upper() in ("NONE", "", "NAN") else t, "class": cls}
    return out


def metrics(items: pd.DataFrame, truth: dict[str, dict], mode: str) -> dict:
    it = items[items["item_id"].isin(truth.keys())]
    total = int(it["spend_cents"].abs().sum()) or 1
    auto = it[it["status"].isin(("auto", "evidence"))]
    correct = [truth[r.item_id]["truth"] == r.part_id for r in auto.itertuples(index=False)]
    wrong = auto[[not c for c in correct]]
    review = it[it["status"] == "review"]
    rev_right = [truth[r.item_id]["truth"] == r.suggestion_part_id for r in review.itertuples(index=False) if r.suggestion_part_id]
    lookalike_wrong = 0
    for r in wrong.itertuples(index=False):
        c = (truth[r.item_id].get("class") or "").lower()
        if "look" in c or "refus" in c or truth[r.item_id]["truth"] is None:
            lookalike_wrong += 1
    return {"mode": mode, "items": int(len(it)),
            "auto_share_spend": float(auto["spend_cents"].abs().sum() / total),
            "precision": (sum(correct) / len(correct)) if correct else None,
            "wrong_links": int(len(wrong)), "wrong_money_cents": int(wrong["spend_cents"].abs().sum()),
            "lookalikes_wrongly_linked": int(lookalike_wrong),
            "sent_to_review": int(len(review)),
            "review_suggestion_right": (sum(rev_right) / len(rev_right)) if rev_right else None}


def text_only(s1, inp: Inputs) -> pd.DataFrame:
    """Baseline: link to the most similar part if similarity clears the auto-link threshold."""
    th = inp.rules["thresholds"]
    rows = []
    for it, res in zip(s1.items.itertuples(index=False), s1.results):
        c = res["candidates"][0] if res["candidates"] else None
        best = max(res["candidates"], key=lambda x: x["text_sim"]) if res["candidates"] else None
        if best and best["text_sim"] >= max(th["auto_link_min_text"], 0.5):
            rows.append({"item_id": it.item_id, "status": "auto", "part_id": best["part_id"], "suggestion_part_id": None, "spend_cents": it.spend_cents})
        elif best and best["text_sim"] >= th["min_similarity"]:
            rows.append({"item_id": it.item_id, "status": "review", "part_id": None, "suggestion_part_id": best["part_id"], "spend_cents": it.spend_cents})
        else:
            rows.append({"item_id": it.item_id, "status": "nomatch", "part_id": None, "suggestion_part_id": None, "spend_cents": it.spend_cents})
    return pd.DataFrame(rows)


def run_proof(inp: Inputs, answer_key: pd.DataFrame, ai=None) -> list[dict]:
    clean = copy.copy(inp)
    clean.decisions = []
    s1 = stage1(clean, ai=ai)
    truth = item_truth(s1.lines, answer_key)
    out = []
    out.append(metrics(text_only(s1, clean), truth, "Text similarity only"))
    # rules only: rungs 1-3, no quantity / price evidence
    no_vol = copy.copy(clean)
    no_vol.volumes = None
    r_rules = stage2(stage1(no_vol, ai=None), _no_price(no_vol))
    out.append(metrics(r_rules["items"], truth, "Rules only"))
    full = stage2(s1, clean)
    out.append(metrics(full["items"], truth, "Full (rules + quantity + price" + (" + timing" if full["timing_on"] else "") + ")"))
    return out


def _no_price(inp: Inputs) -> Inputs:
    i = copy.copy(inp)
    i.rules = copy.deepcopy(inp.rules)
    i.rules["price_band"] = {"low": 0.0, "high": 1e12}
    return i
