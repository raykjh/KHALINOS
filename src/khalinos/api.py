"""Public KHALINOS intake and read-only run status API."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from khalinos.cloud import dispatch_run
from khalinos.models import RunRecord, RunStatus, UserBrief, canonical_sha256
from khalinos.storage import CloudRunStore


app = FastAPI(title="KHALINOS", version="0.1.0")
web_root = Path(__file__).with_name("web")
app.mount("/assets", StaticFiles(directory=web_root), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(web_root / "index.html")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "product": "KHALINOS",
        "model": os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash"),
        "framework": "Google ADK 2.6.2",
        "runtime": "Google Cloud Run",
    }


@app.post("/api/runs", status_code=202)
def create_run(brief: UserBrief) -> dict[str, object]:
    run_id = uuid4().hex
    record = RunRecord(
        run_id=run_id,
        status=RunStatus.QUEUED,
        brief_sha256=canonical_sha256(brief),
        message="The immutable user brief is queued for Cloud execution.",
    )
    store = CloudRunStore()
    store.create(record, brief)
    try:
        dispatch = dispatch_run(run_id)
    except Exception:
        store.update(record.model_copy(update={"status": RunStatus.FAILED, "message": "Cloud dispatch failed."}))
        raise
    return {"record": record.model_dump(mode="json"), "dispatch": dispatch}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    try:
        return CloudRunStore().read_record(run_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc

