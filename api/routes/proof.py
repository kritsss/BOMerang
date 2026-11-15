from __future__ import annotations

from fastapi import APIRouter

import service
from engine.evaluate import run_proof
from llm.client import make_ranker

from .common import clean, project_or_404

router = APIRouter()


@router.get("/projects/{pid}/proof")
def proof(pid: int):
    project_or_404(pid)
    data, _, _ = service.load_data(pid)
    key = data.get("answer_key")
    if key is None or not len(key):
        return {"available": False}
    out = []
    for u in service.spend_uploads(pid):
        inp = service.build_inputs(pid, spend_override=service.load_canonical(u))
        rows = run_proof(inp, key, ai=make_ranker())
        out.append({"spend_file": f"{u.filename}{(' · ' + u.sheet) if u.sheet else ''}", "rows": rows})
    return clean({"available": True, "datasets": out})
