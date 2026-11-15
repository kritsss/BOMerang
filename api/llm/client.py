"""Anthropic client: strict JSON, one retry, cache, guardrails. Optional: without a key, AI is off."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ValidationError

from . import cache, guardrails

TEMPLATE_VERSION = "rank_v1"
PROMPT = (Path(__file__).parent / "prompts" / "rank_v1.txt").read_text()


class RankOut(BaseModel):
    best_part_id: Optional[str] = None
    reason: str = ""
    attributes: dict[str, Optional[str]] = {}


def model_name() -> str:
    return os.environ.get("LLM_MODEL", "claude-sonnet-5-5")


def ai_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("BOMERANG_AI", "on") != "off"


def _call(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(model=model_name(), max_tokens=600, temperature=0,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _parse(text: str) -> RankOut:
    t = text.strip()
    if "{" in t:
        t = t[t.index("{"): t.rindex("}") + 1]
    return RankOut.model_validate(json.loads(t))


def make_ranker(max_items: int | None = None):
    """Return a callable(payload) -> dict | None, or None if AI is off."""
    if not ai_enabled():
        return None
    limit = max_items if max_items is not None else int(os.environ.get("AI_MAX_ITEMS", "200"))
    state = {"n": 0}

    def rank(payload: dict):
        key = cache.cache_key(model_name(), TEMPLATE_VERSION, payload)
        hit = cache.get(key)
        if hit is None:
            if state["n"] >= limit:
                return None
            state["n"] += 1
            prompt = PROMPT.format(payload=json.dumps(payload, ensure_ascii=False, indent=1))
            out = None
            for _ in range(2):  # one retry on invalid output, then skip
                try:
                    out = _parse(_call(prompt))
                    break
                except (ValidationError, ValueError, json.JSONDecodeError):
                    continue
                except Exception:
                    return None
            if out is None:
                return None
            hit = out.model_dump()
            cache.put(key, hit)
        source = f"{payload.get('description','')} {payload.get('supplier_part_no') or ''}"
        cand_ids = {c["part_id"] for c in payload.get("candidates", [])}
        best = hit.get("best_part_id")
        if best not in cand_ids:
            best = None
        attrs = guardrails.filter_attributes(hit.get("attributes") or {}, source, payload.get("attribute_names", []))
        reason = hit.get("reason") or ""
        allowed = json.dumps(payload, ensure_ascii=False)
        if not guardrails.explanation_ok(reason, allowed):
            reason = "AI ranked this part first (its explanation contained numbers not in the data and was hidden)."
        return {"best_part_id": best, "reason": reason, "attributes": attrs}

    return rank
