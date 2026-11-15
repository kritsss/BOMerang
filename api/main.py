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


# ---------------------------------------------------------------------------
# Production: serve the built web app (web/dist) from this same server, so the
# frontend and the API share one address. Set by the root Dockerfile; unset in
# local development, where Vite serves the frontend instead.
_static = os.environ.get("BOMERANG_STATIC_DIR")
if _static and os.path.isfile(os.path.join(_static, "index.html")):
    from pathlib import Path

    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _root = Path(_static).resolve()
    _index = _root / "index.html"
    if (_root / "assets").is_dir():  # hashed build files: cache for a year
        app.mount("/assets", StaticFiles(directory=_root / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        f = (_root / path).resolve()
        if path and f.is_file() and _root in f.parents:  # favicon etc.
            return FileResponse(f)
        # every other path is a client-side route: hand it to the React router
        return FileResponse(_index, headers={"Cache-Control": "no-cache"})

    @app.middleware("http")
    async def _cache_assets(request, call_next):
        resp = await call_next(request)
        if request.url.path.startswith("/assets/") and resp.status_code == 200:
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp
