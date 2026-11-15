from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import service
from store.db import Project, session, select

from .common import project_or_404

router = APIRouter()


class ProjectIn(BaseModel):
    name: str
    display_currency: str = "USD"


class ProjectPatch(BaseModel):
    name: str | None = None
    display_currency: str | None = None
    fx_overrides: dict | None = None
    active_spend_upload_id: int | None = None


def _out(p: Project):
    last = service.latest_run(p.id)
    return {**p.model_dump(), "has_run": last is not None, "last_run_id": last.id if last else None}


@router.get("/projects")
def list_projects():
    with session() as s:
        return [_out(p) for p in s.exec(select(Project).order_by(Project.id)).all()]


@router.post("/projects")
def create_project(body: ProjectIn):
    if not body.name.strip():
        raise HTTPException(400, "Name required")
    with session() as s:
        p = Project(name=body.name.strip(), display_currency=body.display_currency.upper().strip() or "USD")
        s.add(p)
        s.commit()
        s.refresh(p)
    return _out(p)


@router.get("/projects/{pid}")
def get_project(pid: int):
    return _out(project_or_404(pid))


@router.patch("/projects/{pid}")
def patch_project(pid: int, body: ProjectPatch):
    project_or_404(pid)
    with session() as s:
        p = s.get(Project, pid)
        if body.name is not None:
            p.name = body.name
        if body.display_currency:
            p.display_currency = body.display_currency.upper().strip()
        if body.fx_overrides is not None:
            p.fx_overrides = {k.upper(): float(v) for k, v in body.fx_overrides.items() if v not in (None, "")}
        if body.active_spend_upload_id is not None:
            p.active_spend_upload_id = body.active_spend_upload_id
        s.add(p)
        s.commit()
        s.refresh(p)
    return _out(p)


@router.delete("/projects/{pid}")
def delete_project(pid: int):
    project_or_404(pid)
    import shutil
    from store.db import Decision, LearnedRule, RuleVersion, Run, SavedMapping, Upload
    with session() as s:
        for M in (Upload, SavedMapping, RuleVersion, LearnedRule, Decision, Run):
            for r in s.exec(select(M).where(M.project_id == pid)).all():
                s.delete(r)
        s.delete(s.get(Project, pid))
        s.commit()
    shutil.rmtree(service.pdir(pid), ignore_errors=True)
    return {"ok": True}


@router.get("/projects/{pid}/readiness")
def get_readiness(pid: int):
    project_or_404(pid)
    return service.project_readiness(pid)
