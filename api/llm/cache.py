"""LLM response cache keyed by hash(model, prompt template version, input). Reruns are identical and work offline."""
from __future__ import annotations

import hashlib
import json

from store.db import LLMCache, session


def cache_key(model: str, template_version: str, payload: dict) -> str:
    raw = json.dumps({"m": model, "t": template_version, "p": payload}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def get(key: str):
    with session() as s:
        row = s.get(LLMCache, key)
        return row.response if row else None


def put(key: str, response: dict):
    with session() as s:
        s.merge(LLMCache(key=key, response=response))
        s.commit()
