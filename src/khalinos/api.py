"""Public KHALINOS intake and read-only run status API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from khalinos.cloud import dispatch_run
from khalinos.auth import AuthenticationUnavailable, Identity, InvalidIdentity, authenticate_bearer, google_client_id
from khalinos.intake import answer_intake, authorized_brief, inspect_materials, restart_intake, start_intake
from khalinos.intake_storage import CloudIntakeStore
from khalinos.models import (
    IntakeAnswer,
    IntakeCreate,
    IntakeRevision,
    MaterialInspectionRequest,
    ProjectRecord,
    RunRecord,
    RunStatus,
    UserBrief,
    UploadCreate,
    canonical_sha256,
)
from khalinos.projects import CloudProjectStore
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.sixsense import SixSenseAgent
from khalinos.storage import CloudRunStore
from khalinos.uploads import CloudUploadStore


app = FastAPI(title="KHALINOS", version="0.5.0")
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
        "version": "0.5.0",
    }


def require_identity(authorization: Annotated[str | None, Header()] = None) -> Identity:
    try:
        return authenticate_bearer(authorization)
    except AuthenticationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidIdentity as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def queue_run(
    brief: UserBrief,
    *,
    owner_id: str,
    project_id: str,
    project_kind: str,
    source_snapshot=None,
) -> dict[str, object]:
    work_mode = "existing_project_repair" if source_snapshot else "new_product_build"
    toolpack = APPROVED_TOOLPACKS.select(
        project_kind=project_kind,
        work_mode=work_mode,
    )
    binding = toolpack.binding()
    brief = brief.model_copy(update={
        "toolpack_binding": binding,
        "authorized_output_files": list(toolpack.manifest.output.authorized_paths),
    })
    run_id = uuid4().hex
    record = RunRecord(
        run_id=run_id,
        status=RunStatus.QUEUED,
        brief_sha256=canonical_sha256(brief),
        toolpack_binding=binding,
        message="The immutable user brief is queued for Cloud execution.",
        owner_id=owner_id,
        project_id=project_id,
        work_mode=work_mode,
        source_snapshot=source_snapshot,
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
def get_run(run_id: str, identity: Annotated[Identity, Depends(require_identity)]) -> dict[str, object]:
    try:
        record = CloudRunStore().read_record(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    if record.owner_id != identity.owner_id:
        raise HTTPException(status_code=404, detail="run not found")
    return record.model_dump(mode="json")


@app.get("/api/config")
def public_config() -> dict[str, object]:
    client_id = google_client_id()
    return {
        "google_sign_in_enabled": bool(client_id),
        "google_client_id": client_id,
        "judge_demo_enabled": True,
    }


@app.get("/api/demo/project")
def judge_demo_project() -> dict[str, object]:
    return {
        "project_name": "PUZZLE Input Repair",
        "goal": "Fix the project so WASD and arrow-key movement work reliably without changing the existing game rules or visual design.",
        "project_locator": "khalinos://judge-demo/puzzle-input-repair",
        "materials": [
            {"filename": "project.godot", "relative_path": "puzzle/project.godot", "media_type": "text/plain", "size_bytes": 407},
            {"filename": "player.gd", "relative_path": "puzzle/scripts/player.gd", "media_type": "text/plain", "size_bytes": 7316},
            {"filename": "puzzle.exe", "relative_path": "build/puzzle.exe", "media_type": "application/octet-stream", "size_bytes": 109124128},
        ],
        "notice": "This public judge path is a bounded, preloaded example. Sign-in is required to store projects or start paid execution.",
    }


@app.get("/api/auth/me")
def auth_me(identity: Annotated[Identity, Depends(require_identity)]) -> dict[str, str]:
    return {"owner_id": identity.owner_id, "email": identity.email, "name": identity.name}


@app.get("/api/projects")
def list_projects(identity: Annotated[Identity, Depends(require_identity)]) -> list[dict[str, object]]:
    return [item.model_dump(mode="json") for item in CloudProjectStore().list_owned(identity.owner_id)]


@app.get("/api/projects/{project_id}/artifact")
def get_project_artifact(
    project_id: str,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    try:
        project = CloudProjectStore().read_owned(project_id, identity.owner_id)
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
    if project.latest_status != RunStatus.PASSED or project.source_snapshot is None:
        raise HTTPException(status_code=409, detail="project has no verified playable result")
    return CloudRunStore().read_bundle_archive(project.source_snapshot).model_dump(mode="json")


@app.post("/api/uploads", status_code=201)
def create_upload(
    request: UploadCreate,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    try:
        record, session_uri = CloudUploadStore().create_session(request, identity.owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return {
        "upload": record.model_dump(mode="json"),
        "resumable_session_uri": session_uri,
        "required_content_type": "application/zip",
    }


@app.post("/api/uploads/{upload_id}/finalize")
def finalize_upload(
    upload_id: str,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    try:
        return CloudUploadStore().finalize(upload_id, identity.owner_id).model_dump(mode="json")
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail="upload not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/intakes", status_code=201)
async def create_intake(
    request: IntakeCreate,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    try:
        if request.selected_project_id and request.upload_id:
            raise ValueError("choose either a KHALINOS project or one external ZIP")
        source_snapshot = None
        if request.selected_project_id:
            project = CloudProjectStore().read_owned(request.selected_project_id, identity.owner_id)
            if project.source_snapshot is None:
                raise ValueError("the selected project has no verified source snapshot yet")
            source_snapshot = project.source_snapshot
        elif request.upload_id:
            source_snapshot = CloudUploadStore().finalized_snapshot(request.upload_id, identity.owner_id)
        if source_snapshot is not None:
            request = request.model_copy(update={
                "materials": source_snapshot.materials,
                "project_locator": f"gs://{source_snapshot.bucket}/{source_snapshot.object_name}",
            })
        record = await start_intake(
            request,
            store=CloudIntakeStore(),
            agent=SixSenseAgent(),
            owner_id=identity.owner_id,
            source_snapshot=source_snapshot,
        )
        return record.model_dump(mode="json")
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/materials/inspect")
def inspect_submitted_materials(request: MaterialInspectionRequest) -> dict[str, object]:
    """Return advisory static classification; this endpoint never executes submitted files."""
    return inspect_materials(request).model_dump(mode="json")


@app.get("/api/intakes/{intake_id}")
def get_intake(intake_id: str, identity: Annotated[Identity, Depends(require_identity)]) -> dict[str, object]:
    try:
        record = CloudIntakeStore().read(intake_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="intake not found") from exc
    if record.owner_id != identity.owner_id:
        raise HTTPException(status_code=404, detail="intake not found")
    return record.model_dump(mode="json")


@app.post("/api/intakes/{intake_id}/answers")
async def submit_intake_answer(
    intake_id: str,
    answer: IntakeAnswer,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    try:
        if CloudIntakeStore().read(intake_id).owner_id != identity.owner_id:
            raise FileNotFoundError(intake_id)
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
async def revise_intake(
    intake_id: str,
    revision: IntakeRevision,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    try:
        if CloudIntakeStore().read(intake_id).owner_id != identity.owner_id:
            raise FileNotFoundError(intake_id)
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
def authorize_intake(
    intake_id: str,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    store = CloudIntakeStore()
    try:
        intake = store.read(intake_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="intake not found") from exc
    if intake.owner_id != identity.owner_id:
        raise HTTPException(status_code=404, detail="intake not found")
    if intake.status == "authorized" and intake.authorized_run_id:
        return {
            "intake": intake.model_dump(mode="json"),
            "record": CloudRunStore().read_record(intake.authorized_run_id).model_dump(mode="json"),
            "dispatch": {"run_id": intake.authorized_run_id, "asynchronous": True},
        }
    if intake.status != "ready" or intake.preview is None:
        raise HTTPException(status_code=409, detail="SixSense intake is not ready for authorization")
    project_store = CloudProjectStore()
    project_id = intake.selected_project_id or uuid4().hex
    if intake.selected_project_id:
        previous = project_store.read_owned(project_id, identity.owner_id)
        created_at = previous.created_at
        origin = previous.origin
        project_kind = previous.project_kind
    else:
        created_at = intake.created_at
        origin = "external" if intake.material_inspection and intake.material_inspection.source_available else "khalinos"
        detected_kind = intake.material_inspection.project_kind if intake.material_inspection else "unknown"
        project_kind = detected_kind if detected_kind in {"godot", "unity", "web"} else "browser"
    result = queue_run(
        authorized_brief(intake.preview),
        owner_id=identity.owner_id,
        project_id=project_id,
        project_kind=project_kind,
        source_snapshot=intake.source_snapshot,
    )
    run_id = result["record"]["run_id"]
    project_store.prepare(ProjectRecord(
        project_id=project_id,
        owner_id=identity.owner_id,
        display_name=intake.project_name,
        project_kind=project_kind,
        origin=origin,
        latest_run_id=run_id,
        latest_status=RunStatus.QUEUED,
        source_snapshot=intake.source_snapshot,
        created_at=created_at,
    ))
    intake = intake.model_copy(update={"status": "authorized", "authorized_run_id": run_id})
    store.update(intake)
    return {"intake": intake.model_dump(mode="json"), **result}
