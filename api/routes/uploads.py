from __future__ import annotations

import csv
import hashlib
import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

import service
from engine.mapping import FILE_TYPE_LABEL, SCHEMA, apply_mapping, suggest_file_type, suggest_mapping
from engine.normalize import basic_clean
from engine.rules import suggest_hard_attributes
from store.db import SavedMapping, Upload, select, session

from .common import clean, project_or_404, records

router = APIRouter()


@router.get("/schema")
def schema():
    return {"types": [{"key": t, "label": FILE_TYPE_LABEL[t],
                       "fields": [{"name": f, "required": r} for f, r, _ in fields]} for t, fields in SCHEMA.items()]}


def _read_csv(raw: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        sep = dialect.delimiter
    except csv.Error:
        sep = ","
    return pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False, na_values=[""])


def _sig(cols) -> str:
    return hashlib.sha1("|".join(sorted(basic_clean(str(c)) for c in cols)).encode()).hexdigest()[:16]


def _upload_out(u: Upload, df: pd.DataFrame | None = None) -> dict:
    if df is None:
        df = pd.read_pickle(u.raw_path)
    saved = None
    with session() as s:
        sm = s.exec(select(SavedMapping).where(SavedMapping.project_id == u.project_id, SavedMapping.header_sig == u.header_sig)
                    .order_by(SavedMapping.id.desc())).first()
    if sm:
        saved = {"file_type": sm.file_type, "mapping": sm.mapping, "attribute_columns": sm.attribute_columns}
    ft = u.file_type or (saved["file_type"] if saved else suggest_file_type(df, u.sheet or u.filename))
    mapping = u.mapping if u.file_type else (saved["mapping"] if saved and saved["file_type"] == ft else suggest_mapping(df, ft))
    used = {v for v in mapping.values() if v}
    attr_cands = [c for c in df.columns if c not in used]
    attrs = u.attribute_columns if u.file_type == "master" else (saved["attribute_columns"] if saved and saved["file_type"] == "master" else attr_cands)
    return {"id": u.id, "filename": u.filename, "sheet": u.sheet, "status": u.status, "n_rows": u.n_rows, "errors": u.errors,
            "columns": [str(c) for c in df.columns], "preview": records(df.head(5).astype(object)),
            "file_type": u.file_type, "suggested_type": ft, "mapping": mapping, "saved_mapping": saved is not None,
            "attribute_candidates": attr_cands, "attribute_columns": attrs,
            "hard_suggestion": suggest_hard_attributes(attrs or [])}


@router.post("/projects/{pid}/uploads")
async def upload(pid: int, files: list[UploadFile] = File(...)):
    project_or_404(pid)
    out = []
    for f in files:
        raw = await f.read()
        name = f.filename or "upload"
        sheets: list[tuple[str, pd.DataFrame]] = []
        try:
            if name.lower().endswith((".xlsx", ".xlsm", ".xls")):
                book = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype=str)
                sheets = [(k, v) for k, v in book.items() if len(v.columns) and len(v)]
            else:
                sheets = [("", _read_csv(raw))]
        except Exception as e:
            raise HTTPException(400, f"Could not read {name}: {e}")
        for sheet, df in sheets:
            df = df.dropna(how="all")
            df.columns = [str(c).strip() for c in df.columns]
            df = df.loc[:, [c for c in df.columns if not c.lower().startswith("unnamed:") or df[c].notna().any()]]
            with session() as s:
                u = Upload(project_id=pid, filename=name, sheet=sheet, header_sig=_sig(df.columns), n_rows=len(df))
                s.add(u)
                s.commit()
                s.refresh(u)
                path = service.pdir(pid) / "uploads" / f"{u.id}_raw.pkl"
                path.parent.mkdir(exist_ok=True)
                df.to_pickle(path)
                u.raw_path = str(path)
                s.add(u)
                s.commit()
            out.append(_upload_out(u, df))
    return out


@router.get("/projects/{pid}/uploads")
def list_uploads(pid: int):
    project_or_404(pid)
    return [_upload_out(u) for u in service.uploads(pid)]


@router.get("/projects/{pid}/uploads/{uid}/suggest")
def suggest(pid: int, uid: int, file_type: str):
    u = _get(pid, uid)
    df = pd.read_pickle(u.raw_path)
    if file_type not in SCHEMA:
        raise HTTPException(400, "Unknown file type")
    m = suggest_mapping(df, file_type)
    used = {v for v in m.values() if v}
    attrs = [c for c in df.columns if c not in used]
    return {"mapping": m, "attribute_candidates": attrs, "hard_suggestion": suggest_hard_attributes(attrs)}


class MappingIn(BaseModel):
    file_type: str
    mapping: dict[str, str | None]
    attribute_columns: list[str] = []
    hard_attributes: list[str] | None = None


def _get(pid: int, uid: int) -> Upload:
    with session() as s:
        u = s.get(Upload, uid)
    if u is None or u.project_id != pid:
        raise HTTPException(404, "Upload not found")
    return u


@router.post("/projects/{pid}/uploads/{uid}/mapping")
def save_mapping(pid: int, uid: int, body: MappingIn):
    u = _get(pid, uid)
    if body.file_type not in SCHEMA:
        raise HTTPException(400, "Unknown file type")
    df = pd.read_pickle(u.raw_path)
    canon, errors = apply_mapping(df, body.file_type, body.mapping, body.attribute_columns)
    if errors:
        raise HTTPException(400, " ".join(errors))
    cpath = service.pdir(pid) / "uploads" / f"{uid}_canon.pkl"
    canon.to_pickle(cpath)
    with session() as s:
        u = s.get(Upload, uid)
        u.file_type, u.mapping, u.attribute_columns = body.file_type, body.mapping, body.attribute_columns if body.file_type == "master" else []
        u.status, u.canonical_path, u.errors, u.n_rows = "mapped", str(cpath), [], len(canon)
        s.add(u)
        # single-type files: the newest mapped upload replaces older ones
        if body.file_type != "spend":
            for old in s.exec(select(Upload).where(Upload.project_id == pid, Upload.file_type == body.file_type, Upload.id != uid)).all():
                old.status = "replaced"
                s.add(old)
        s.add(SavedMapping(project_id=pid, file_type=body.file_type, header_sig=u.header_sig, mapping=body.mapping,
                           attribute_columns=body.attribute_columns))
        if body.file_type == "spend":
            from store.db import Project
            p = s.get(Project, pid)
            p.active_spend_upload_id = uid
            s.add(p)
        s.commit()
    if body.file_type == "master" and body.hard_attributes is not None:
        _, rules = service.get_rules(pid)
        ha = dict(rules.get("hard_attributes") or {})
        ha["*"] = [a for a in body.hard_attributes if a in body.attribute_columns]
        rules["hard_attributes"] = ha
        service.save_rules(pid, rules, "analyst", "Hard attributes confirmed at column mapping")
    return _upload_out(_get(pid, uid))


@router.delete("/projects/{pid}/uploads/{uid}")
def delete_upload(pid: int, uid: int):
    _get(pid, uid)
    with session() as s:
        s.delete(s.get(Upload, uid))
        s.commit()
    return {"ok": True}
