#!/usr/bin/env python3
"""
HTTP API of the web app, and in production also the server of its built
frontend (web/dist).

Run from the repository root:
    uv run uvicorn --app-dir src web_api:app --host 0.0.0.0 --port 8600
"""

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import web_store as store

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Prepares the voter-flow estimates, so that nobody waits for them; with
    # the estimates already on disk this takes a moment. It runs as a separate
    # process because the computation would slow down every request served
    # meanwhile. VOLBY_PRECOMPUTE=0 leaves the estimates to be computed when
    # first opened.
    worker = None
    if os.environ.get("VOLBY_PRECOMPUTE", "1") != "0":
        worker = subprocess.Popen([sys.executable, str(Path(__file__).with_name("web_store.py"))])
    yield
    if worker and worker.poll() is None:
        worker.terminate()


app = FastAPI(
    title="Volební analýza",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.exception_handler(store.NotFound)
async def not_found(_, error: store.NotFound):
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.get("/api/config")
def config():
    # Address of the original Streamlit app, offered as a fallback when set
    return {"legacyUrl": os.environ.get("VOLBY_LEGACY_URL") or None}


@app.get("/api/elections")
def elections():
    return store.list_elections()


@app.get("/api/elections/{election_id}/overview")
def overview(election_id: str):
    return store.election_overview(election_id)


@app.get("/api/elections/{election_id}/councils")
def councils(election_id: str):
    return store.list_councils(election_id)


@app.get("/api/elections/{election_id}/councils/{code}")
def council(election_id: str, code: str):
    return store.council(election_id, code)


@app.get("/api/elections/{election_id}/councils/{code}/boundaries")
def boundaries(election_id: str, code: str):
    return store.boundaries(election_id, code)


@app.get("/api/elections/{election_id}/councils/{code}/comparison")
def comparison(election_id: str, code: str, area: Optional[str] = None):
    return store.comparison(election_id, code, area)


@app.get("/api/elections/{election_id}/councils/{code}/candidates")
def candidates(election_id: str, code: str):
    return store.candidates(election_id, code)


DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        """Every other address belongs to the single-page app."""
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = DIST / path
        if path and file.is_file() and DIST in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
