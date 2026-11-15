from __future__ import annotations

import math

import numpy as np
import pandas as pd
from fastapi import HTTPException

import service
from store.db import Project, session


def project_or_404(pid: int) -> Project:
    with session() as s:
        p = s.get(Project, pid)
    if p is None:
        raise HTTPException(404, "Project not found")
    return p


def result_or_404(pid: int) -> dict:
    project_or_404(pid)
    r = service.result(pid)
    if r is None:
        raise HTTPException(409, "No run yet. Upload files and link them first.")
    return r


def clean(v):
    """JSON-safe conversion of numpy/pandas values."""
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [clean(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(v, np.bool_):
        return bool(v)
    if v is pd.NaT:
        return None
    if isinstance(v, np.ndarray):
        return [clean(x) for x in v.tolist()]
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def records(df: pd.DataFrame, cols: list[str] | None = None) -> list[dict]:
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    return [clean(r) for r in df.to_dict("records")]
