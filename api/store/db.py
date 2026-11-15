"""SQLite models. The database is created empty: no migration inserts business data."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATA_DIR = Path(os.environ.get("BOMERANG_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.environ.get("BOMERANG_DB_URL", f"sqlite:///{DATA_DIR / 'bomerang.db'}")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    display_currency: str = "USD"
    fx_overrides: dict = Field(default_factory=dict, sa_column=Column(JSON))
    active_spend_upload_id: Optional[int] = None
    created_at: str = Field(default_factory=now)


class Upload(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    filename: str
    sheet: str = ""
    header_sig: str = ""
    raw_path: str = ""
    canonical_path: str = ""
    file_type: Optional[str] = None
    mapping: dict = Field(default_factory=dict, sa_column=Column(JSON))
    attribute_columns: list = Field(default_factory=list, sa_column=Column(JSON))
    n_rows: int = 0
    status: str = "needs_mapping"
    errors: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: str = Field(default_factory=now)


class SavedMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    file_type: str
    header_sig: str
    mapping: dict = Field(default_factory=dict, sa_column=Column(JSON))
    attribute_columns: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: str = Field(default_factory=now)


class RuleVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    version: int
    rules: dict = Field(default_factory=dict, sa_column=Column(JSON))
    who: str = ""
    why: str = ""
    loosened: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: str = Field(default_factory=now)


class LearnedRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    kind: str
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))
    who: str = ""
    why: str = ""
    decision_id: Optional[int] = None
    active: bool = True
    created_at: str = Field(default_factory=now)


class Decision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    item_id: str
    item_key: str
    action: str
    part_id: Optional[str] = None
    unit_factor: Optional[float] = None
    purchase_uom: Optional[str] = None
    base_uom: Optional[str] = None
    reason: str = ""
    who: str = ""
    override_refusal: bool = False
    undone: bool = False
    spend_cents: int = 0
    description: str = ""
    supplier: str = ""
    created_at: str = Field(default_factory=now)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    kind: str = "full"
    status: str = "queued"
    progress: float = 0.0
    message: str = ""
    error: str = ""
    rule_version: int = 0
    stage1_path: str = ""
    result_path: str = ""
    parent_run_id: Optional[int] = None
    summary: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: str = Field(default_factory=now)
    finished_at: str = ""


class LLMCache(SQLModel, table=True):
    key: str = Field(primary_key=True)
    response: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: str = Field(default_factory=now)


engine = create_engine(DB_URL, connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def session() -> Session:
    return Session(engine, expire_on_commit=False)


__all__ = ["Project", "Upload", "SavedMapping", "RuleVersion", "LearnedRule", "Decision", "Run", "LLMCache",
           "engine", "init_db", "session", "select", "DATA_DIR", "now"]
