"""BOMerang API."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm.client import ai_enabled, model_name
from routes import export, parts, projects, proof, review, rules, runs, simulate, uploads
from store.db import init_db

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="BOMerang API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True, "ai_on": ai_enabled(), "model": model_name() if ai_enabled() else None}


for r in (projects, uploads, runs, review, parts, simulate, rules, proof, export):
    app.include_router(r.router, prefix="/api")
