"""Service layer: projects, data loading, runs and their cached results."""
from __future__ import annotations

import hashlib
import json
import pickle
import threading
import traceback
from collections import OrderedDict
from pathlib import Path

import pandas as pd

from engine import costing
from engine.ledger import CLASS_LABEL
from engine.pipeline import Inputs, stage1, stage2
from engine.readiness import readiness
from engine.rules import default_rules, merge_rules
from llm.client import ai_enabled, make_ranker
from store.db import (DATA_DIR, Decision, LearnedRule, Project, RuleVersion, Run, Upload, now, select, session)

_results: "OrderedDict[int, dict]" = OrderedDict()
_lock = threading.Lock()
_run_lock: dict[int, threading.Lock] = {}

ENGINE_VERSION = "2"  # bump when matching logic changes, so cached matching results are recomputed

SINGLE_TYPES = ["bom", "products", "master", "volumes", "suppliers", "conversions", "fx", "xrefs", "answer_key"]


def pdir(pid: int) -> Path:
    d = DATA_DIR / "projects" / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- rules -----------------------------------------------------------------

def get_rules(pid: int) -> tuple[int, dict]:
    with session() as s:
        rv = s.exec(select(RuleVersion).where(RuleVersion.project_id == pid).order_by(RuleVersion.version.desc())).first()
    if rv is None:
        return 0, default_rules()
    return rv.version, merge_rules(rv.rules)


def save_rules(pid: int, rules: dict, who: str, why: str, loosened: list | None = None) -> RuleVersion:
    v, _ = get_rules(pid)
    with session() as s:
        rv = RuleVersion(project_id=pid, version=v + 1, rules=rules, who=who, why=why, loosened=loosened or [])
        s.add(rv)
        s.commit()
        s.refresh(rv)
        return rv


def learned_rules(pid: int, active_only=True) -> list[dict]:
    with session() as s:
        q = select(LearnedRule).where(LearnedRule.project_id == pid)
        if active_only:
            q = q.where(LearnedRule.active == True)  # noqa: E712
        rows = s.exec(q.order_by(LearnedRule.id)).all()
    return [{"id": r.id, "kind": r.kind, "value": r.value, "who": r.who, "why": r.why, "created_at": r.created_at,
             "decision_id": r.decision_id, "active": r.active} for r in rows]


def decisions(pid: int, active_only=True) -> list[dict]:
    with session() as s:
        q = select(Decision).where(Decision.project_id == pid)
        if active_only:
            q = q.where(Decision.undone == False)  # noqa: E712
        rows = s.exec(q.order_by(Decision.id)).all()
    out = {}
    allr = []
    for r in rows:
        d = r.model_dump()
        allr.append(d)
        out[r.item_id] = d  # latest decision per item wins
    return list(out.values()) if active_only else allr


# --- data --------------------------------------------------------------------

def uploads(pid: int) -> list[Upload]:
    with session() as s:
        return s.exec(select(Upload).where(Upload.project_id == pid).order_by(Upload.id)).all()


def load_canonical(u: Upload) -> pd.DataFrame:
    return pd.read_pickle(u.canonical_path)


def load_data(pid: int) -> tuple[dict, list[str], Project]:
    with session() as s:
        proj = s.get(Project, pid)
    ups = [u for u in uploads(pid) if u.status == "mapped"]
    data: dict = {t: None for t in SINGLE_TYPES + ["spend"]}
    attrs: list[str] = []
    for u in ups:
        if u.file_type in SINGLE_TYPES:
            data[u.file_type] = load_canonical(u)
            if u.file_type == "master":
                attrs = list(u.attribute_columns or [])
    spend_ups = [u for u in ups if u.file_type == "spend"]
    if spend_ups:
        act = next((u for u in spend_ups if u.id == proj.active_spend_upload_id), spend_ups[-1])
        data["spend"] = load_canonical(act)
    return data, attrs, proj


def spend_uploads(pid: int) -> list[Upload]:
    return [u for u in uploads(pid) if u.status == "mapped" and u.file_type == "spend"]


def data_signature(pid: int) -> str:
    ups = [u for u in uploads(pid) if u.status == "mapped"]
    with session() as s:
        proj = s.get(Project, pid)
    raw = json.dumps({"u": [(u.id, u.file_type, u.mapping, u.attribute_columns) for u in ups], "c": proj.display_currency,
                      "fx": proj.fx_overrides, "a": proj.active_spend_upload_id}, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def build_inputs(pid: int, with_decisions=True, rules: dict | None = None, spend_override: pd.DataFrame | None = None) -> Inputs:
    data, attrs, proj = load_data(pid)
    _, r = get_rules(pid)
    if rules is not None:
        r = rules
    return Inputs(bom=data["bom"], spend=spend_override if spend_override is not None else data["spend"], products=data["products"],
                  master=data["master"], volumes=data["volumes"], suppliers=data["suppliers"], conversions=data["conversions"],
                  fx=data["fx"], xrefs=data["xrefs"], attribute_columns=attrs, display_currency=proj.display_currency,
                  fx_overrides=proj.fx_overrides or {}, rules=r, learned=learned_rules(pid),
                  decisions=decisions(pid) if with_decisions else [])


def project_readiness(pid: int) -> dict:
    data, attrs, proj = load_data(pid)
    _, r = get_rules(pid)
    rd = readiness(data, proj.display_currency, proj.fx_overrides or {}, attrs, r.get("hard_attributes", {}), ai_enabled(), r)
    rd["files"] = [{"id": u.id, "filename": u.filename, "sheet": u.sheet, "file_type": u.file_type, "n_rows": u.n_rows,
                    "status": u.status} for u in uploads(pid)]
    rd["display_currency"] = proj.display_currency
    return rd


# --- runs --------------------------------------------------------------------

def _stage1_key(pid: int, rv: int, learned: list[dict], ai_on: bool) -> str:
    raw = json.dumps({"e": ENGINE_VERSION, "d": data_signature(pid), "r": rv, "l": [(l["id"], l["kind"]) for l in learned if l["kind"] != "unit"], "ai": ai_on},
                     sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _update_run(rid: int, **kw):
    with session() as s:
        r = s.get(Run, rid)
        for k, v in kw.items():
            setattr(r, k, v)
        s.add(r)
        s.commit()


def start_full_run(pid: int, background=True) -> int:
    rv, _ = get_rules(pid)
    with session() as s:
        run = Run(project_id=pid, kind="full", status="running", rule_version=rv, message="Starting")
        s.add(run)
        s.commit()
        s.refresh(run)
    if background:
        threading.Thread(target=_execute_full, args=(pid, run.id), daemon=True).start()
    else:
        _execute_full(pid, run.id)
    return run.id


def _execute_full(pid: int, rid: int):
    lock = _run_lock.setdefault(pid, threading.Lock())
    with lock:
        try:
            inp = build_inputs(pid)
            if inp.bom is None or inp.spend is None:
                raise ValueError("Upload a BOM and a spend file first.")
            rd = project_readiness(pid)
            if not rd["can_run"]:
                raise ValueError(" ".join(rd["blocking"]))
            ai = make_ranker()
            key = _stage1_key(pid, _run_rule_version(rid), inp.learned, ai is not None)
            path = pdir(pid) / "stage1" / f"{key}.pkl"
            path.parent.mkdir(exist_ok=True)

            def prog(msg, frac):
                _update_run(rid, message=msg, progress=frac)

            if path.exists():
                prog("Reusing matching results", 0.5)
                s1 = pickle.loads(path.read_bytes())
            else:
                s1 = stage1(inp, ai=ai, progress=prog)
                path.write_bytes(pickle.dumps(s1))
            _finish(pid, rid, s1, inp, str(path))
        except Exception as e:  # report the failure on the run
            _update_run(rid, status="failed", error=f"{e}", message="Failed", finished_at=now())
            traceback.print_exc()


def _run_rule_version(rid: int) -> int:
    with session() as s:
        return s.get(Run, rid).rule_version


def _finish(pid: int, rid: int, s1, inp: Inputs, s1_path: str):
    res = stage2(s1, inp)
    res["bom_cost"] = costing.bom_cost(s1.tree, s1.products, s1.parts, res["part_alloc"], res["ledger"], res["items"])
    res.update(parts=s1.parts, tree=s1.tree, leaves=s1.leaves, products=s1.products, req_pp=s1.req_pp, has_volumes=s1.has_volumes,
               ai_used=s1.ai_used, ai_count=s1.ai_count, display_currency=inp.display_currency, volumes=inp.volumes)
    path = pdir(pid) / "runs" / f"{rid}.pkl"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(pickle.dumps(res))
    summ = make_summary(res)
    summ["rule_version"] = _run_rule_version(rid)
    _update_run(rid, status="done", progress=1.0, message="Done", stage1_path=s1_path, result_path=str(path), summary=summ, finished_at=now())
    with _lock:
        _results[rid] = res
        while len(_results) > 6:
            _results.popitem(last=False)


def light_run(pid: int) -> int:
    """Re-apply decisions and checks on the latest matching results (fast)."""
    last = latest_run(pid)
    if last is None:
        raise ValueError("No run yet.")
    inp = build_inputs(pid)
    s1 = pickle.loads(Path(last.stage1_path).read_bytes())
    with session() as s:
        run = Run(project_id=pid, kind="light", status="running", rule_version=last.rule_version, parent_run_id=last.id)
        s.add(run)
        s.commit()
        s.refresh(run)
    _finish(pid, run.id, s1, inp, last.stage1_path)
    return run.id


def latest_run(pid: int, done_only=True) -> Run | None:
    with session() as s:
        q = select(Run).where(Run.project_id == pid)
        if done_only:
            q = q.where(Run.status == "done")
        return s.exec(q.order_by(Run.id.desc())).first()


def result(pid: int, rid: int | None = None) -> dict | None:
    run = latest_run(pid) if rid is None else None
    if rid is None:
        if run is None:
            return None
        rid = run.id
    with _lock:
        if rid in _results:
            return _results[rid]
    with session() as s:
        r = s.get(Run, rid)
    if r is None or not r.result_path or not Path(r.result_path).exists():
        return None
    res = pickle.loads(Path(r.result_path).read_bytes())
    with _lock:
        _results[rid] = res
    return res


def make_summary(res: dict) -> dict:
    items = res["items"]
    lad = res["ladder"]
    s = res["summary"]
    n = len(items)
    auto = lad["auto_total"]
    review = lad["review"]
    refused = lad["refused"]
    waiting = int(items.loc[items["status"] == "review", "spend_cents"].sum())
    return {"ladder": lad, "ledger": s, "items": n, "auto": auto, "review": review, "refused": refused,
            "human": lad["human"], "waiting_cents": waiting, "has_volumes": res["has_volumes"], "ai_used": res["ai_used"],
            "display_currency": res["display_currency"], "timing_on": res.get("timing_on", False),
            "headline": f"{auto} of {n} spend items linked automatically.",
            "subline": f"{review} need your eyes. {refused} were refused."}


def class_label(k: str) -> str:
    return CLASS_LABEL.get(k, k)
