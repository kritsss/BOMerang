from __future__ import annotations

import copy

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import service
from engine.evaluate import item_truth
from engine.learning import describe
from engine.pipeline import stage1, stage2
from engine.rules import default_rules, merge_rules
from llm.client import make_ranker
from store.db import LearnedRule, RuleVersion, select, session

from .common import clean, project_or_404

router = APIRouter()


@router.get("/projects/{pid}/rules")
def get_rules(pid: int):
    project_or_404(pid)
    v, r = service.get_rules(pid)
    data, attrs, _ = service.load_data(pid)
    cats = []
    if data.get("master") is not None and "category" in data["master"]:
        cats = sorted({str(c) for c in data["master"]["category"].dropna()})
    return {"version": v, "rules": r, "attribute_columns": attrs, "categories": cats, "defaults": default_rules()}


@router.get("/projects/{pid}/rules/versions")
def versions(pid: int):
    with session() as s:
        rows = s.exec(select(RuleVersion).where(RuleVersion.project_id == pid).order_by(RuleVersion.version.desc())).all()
    return [{"version": r.version, "who": r.who, "why": r.why, "created_at": r.created_at, "loosened": r.loosened} for r in rows]


class RulesIn(BaseModel):
    rules: dict
    who: str = "analyst"
    why: str = ""


def _loosened(old: dict, new: dict) -> list[str]:
    out = []
    oh, nh = old.get("hard_attributes") or {}, new.get("hard_attributes") or {}
    for cat, attrs in oh.items():
        for a in attrs:
            if a not in (nh.get(cat) if cat in nh else nh.get("*", [])):
                out.append(f"{a} no longer hard for {'all categories' if cat == '*' else cat}")
    ob, nb = old.get("price_band", {}), new.get("price_band", {})
    if nb.get("low", 0) < ob.get("low", 0) or nb.get("high", 0) > ob.get("high", 0):
        out.append("price band widened")
    return out


def _diff(old: dict, new: dict, truth: dict | None) -> dict:
    a, b = old["items"].set_index("item_id"), new["items"].set_index("item_id")
    linked = ("auto", "evidence", "human")
    adds = removes = to_review = from_review = changed = 0
    for iid in a.index:
        sa, sb = a.at[iid, "status"], b.at[iid, "status"] if iid in b.index else "nomatch"
        la, lb = sa in linked, sb in linked
        if lb and not la:
            adds += 1
        elif la and not lb:
            removes += 1
        elif la and lb and a.at[iid, "part_id"] != b.at[iid, "part_id"]:
            changed += 1
        if sb == "review" and sa != "review":
            to_review += 1
        if sa == "review" and sb != "review":
            from_review += 1
    out = {"adds": adds, "removes": removes, "changed": changed, "to_review": to_review, "from_review": from_review,
           "explained_before": old["summary"]["explained_share"], "explained_after": new["summary"]["explained_share"]}
    if truth:
        def wrong(items):
            w = 0
            for r in items.itertuples(index=False):
                if r.status in linked and r.item_id in truth and truth[r.item_id]["truth"] != r.part_id:
                    w += 1
            return w
        out["wrong_before"] = wrong(old["items"])
        out["wrong_after"] = wrong(new["items"])
    return out


@router.post("/projects/{pid}/rules/preview")
def preview(pid: int, body: RulesIn):
    project_or_404(pid)
    cur = service.result(pid)
    if cur is None:
        raise HTTPException(409, "Link your data once before previewing rule changes.")
    new_rules = merge_rules(body.rules)
    inp = service.build_inputs(pid, rules=new_rules)
    s1 = stage1(inp, ai=make_ranker())
    new = stage2(s1, inp)
    data, _, _ = service.load_data(pid)
    truth = item_truth(s1.lines, data["answer_key"]) if data.get("answer_key") is not None else None
    _, old_rules = service.get_rules(pid)
    out = _diff(cur, new, truth)
    out["loosened"] = _loosened(old_rules, new_rules)
    return clean(out)


@router.post("/projects/{pid}/rules")
def apply(pid: int, body: RulesIn):
    project_or_404(pid)
    _, old = service.get_rules(pid)
    new = merge_rules(body.rules)
    loos = _loosened(old, new)
    if loos and not body.why.strip():
        raise HTTPException(400, "Loosening a hard attribute or the price band needs a written reason.")
    rv = service.save_rules(pid, new, body.who, body.why, loos)
    rid = None
    if service.latest_run(pid) is not None:
        rid = service.start_full_run(pid)
    return {"version": rv.version, "run_id": rid, "loosened": loos}


@router.get("/projects/{pid}/learned")
def learned(pid: int):
    rows = service.learned_rules(pid, active_only=False)
    for r in rows:
        r["text"] = describe(r)
    return rows


@router.delete("/projects/{pid}/learned/{lid}")
def remove_learned(pid: int, lid: int):
    with session() as s:
        r = s.get(LearnedRule, lid)
        if r is None or r.project_id != pid:
            raise HTTPException(404, "Not found")
        r.active = False
        s.add(r)
        s.commit()
    rid = service.start_full_run(pid) if service.latest_run(pid) else None
    return {"ok": True, "run_id": rid}
