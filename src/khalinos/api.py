"""Public KHALINOS intake and read-only run status API."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from khalinos.cloud import dispatch_run
from khalinos.intake import answer_intake, authorized_brief, restart_intake, start_intake
from khalinos.intake_storage import CloudIntakeStore
from khalinos.models import (
    IntakeAnswer,
    IntakeCreate,
    IntakeRevision,
    RunRecord,
    RunStatus,
    UserBrief,
    canonical_sha256,
)
from khalinos.sixsense import SixSenseAgent
from khalinos.storage import CloudRunStore


app = FastAPI(title="KHALINOS", version="0.3.1")
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


def queue_run(brief: UserBrief) -> dict[str, object]:
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


@app.post("/api/intakes", status_code=201)
async def create_intake(request: IntakeCreate) -> dict[str, object]:
    try:
        record = await start_intake(request, store=CloudIntakeStore(), agent=SixSenseAgent())
        return record.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/intakes/{intake_id}")
def get_intake(intake_id: str) -> dict[str, object]:
    try:
        return CloudIntakeStore().read(intake_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="intake not found") from exc


@app.post("/api/intakes/{intake_id}/answers")
async def submit_intake_answer(intake_id: str, answer: IntakeAnswer) -> dict[str, object]:
    try:
        record = await answer_intake(
            intake_id,
            answer,
            store=CloudIntakeStore(),
            agent=SixSenseAgent(),
        )
        return record.model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="intake not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/intakes/{intake_id}/revise", status_code=201)
async def revise_intake(intake_id: str, revision: IntakeRevision) -> dict[str, object]:
    try:
        record = await restart_intake(
            intake_id,
            revision,
            store=CloudIntakeStore(),
            agent=SixSenseAgent(),
        )
        return record.model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="intake not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/intakes/{intake_id}/authorize", status_code=202)
def authorize_intake(intake_id: str) -> dict[str, object]:
    store = CloudIntakeStore()
    try:
        intake = store.read(intake_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="intake not found") from exc
    if intake.status == "authorized" and intake.authorized_run_id:
        return {
            "intake": intake.model_dump(mode="json"),
            "record": CloudRunStore().read_record(intake.authorized_run_id).model_dump(mode="json"),
            "dispatch": {"run_id": intake.authorized_run_id, "asynchronous": True},
        }
    if intake.status != "ready" or intake.preview is None:
        raise HTTPException(status_code=409, detail="SixSense intake is not ready for authorization")
    result = queue_run(authorized_brief(intake.preview))
    run_id = result["record"]["run_id"]
    intake = intake.model_copy(update={"status": "authorized", "authorized_run_id": run_id})
    store.update(intake)
    return {"intake": intake.model_dump(mode="json"), **result}
