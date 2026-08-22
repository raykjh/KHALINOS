"""Public KHALINOS intake and read-only run status API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from khalinos.cloud import dispatch_run
from khalinos.execution_telemetry import execution_telemetry
from khalinos.auth import AuthenticationUnavailable, Identity, InvalidIdentity, authenticate_bearer, google_client_id
from khalinos.intake import answer_intake, authorized_brief, inspect_materials, reroute_intake, restart_intake, source_payloads, start_intake
from khalinos.intake_storage import CloudIntakeStore
from khalinos.models import (
    IntakeAnswer,
    IntakeCreate,
    IntakeReroute,
    IntakeRevision,
    MaterialInspectionRequest,
    ProjectRecord,
    RouteRecommendationRequest,
    RunRecord,
    RunStatus,
    UserBrief,
    UploadCreate,
    canonical_sha256,
)
from khalinos.projects import CloudProjectStore
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.routing import RouteAdvisor
from khalinos.sixsense import SixSenseAgent
from khalinos.storage import CloudRunStore
from khalinos.toolpacks import ToolPackBinding
from khalinos.uploads import CloudUploadStore


app = FastAPI(title="KHALINOS", version="0.6.0")
web_root = Path(__file__).with_name("web")
app.mount("/assets", StaticFiles(directory=web_root), name="assets")


def validate_godot_topology_brief(brief: UserBrief) -> None:
    """Keep the public Godot path inside evidence the approved adapter can actually prove."""
    observable_terms = (
        "screen", "overlay", "scene", "region", "topology", "navigation",
        "transition", "open", "load", "reach", "start",
    )
    unsupported_terms = (
        "gameplay", "combat", "enemy", "player movement", "keyboard input",
        "physics", "animation", "save game", "score", "puzzle logic",
        "3d model", "asset generation", "multiplayer", "audio playback",
    )
    for criterion in brief.acceptance_criteria:
        normalized = " ".join(criterion.casefold().split())
        if any(term in normalized for term in unsupported_terms):
            raise ValueError(f"Godot topology evidence cannot verify this criterion: {criterion}")
        if not any(term in normalized for term in observable_terms):
            raise ValueError(f"Godot topology criteria must be screen/load/navigation observations: {criterion}")


def validate_godot_visual_brief(brief: UserBrief) -> None:
    """Bind visual-prototype completion to evidence the real renderer can observe."""
    observable_terms = (
        "visual", "appearance", "style", "screen", "scene", "layout", "composition",
        "palette", "readable", "visible", "render", "navigation", "transition", "open", "load",
    )
    unsupported_terms = (
        "gameplay", "combat", "enemy ai", "player movement", "physics", "save game",
        "score", "puzzle logic", "multiplayer", "audio playback",
    )
    for criterion in brief.acceptance_criteria:
        normalized = " ".join(criterion.casefold().split())
        if any(term in normalized for term in unsupported_terms):
            raise ValueError(f"Godot visual-prototype evidence cannot verify this criterion: {criterion}")
        if not any(term in normalized for term in observable_terms):
            raise ValueError(
                f"Godot visual-prototype criteria must be visible render or screen-flow observations: {criterion}"
            )


def validate_godot_gameplay_brief(brief: UserBrief) -> None:
    """Bind the gameplay route to the mechanics its deterministic adapter can prove."""
    observable_terms = (
        "game", "play", "movement", "move", "formation", "hero", "enemy", "spawn",
        "attack", "combat", "ability", "skill", "health", "damage", "heal", "shield",
        "record", "experience", "level", "choice", "survival", "victory", "defeat",
        "session", "visual", "render", "screen", "promotion", "profession", "upgrade",
        "rank", "grade", "alternative", "random", "seed",
    )
    unsupported_terms = (
        "3d", "multiplayer", "network", "server", "backend", "plugin", "storefront",
        "steam", "console export", "procedural world", "open world", "save game",
    )
    for criterion in brief.acceptance_criteria:
        normalized = " ".join(criterion.casefold().split())
        if any(term in normalized for term in unsupported_terms):
            raise ValueError(f"Godot gameplay evidence cannot verify this criterion: {criterion}")
        if not any(term in normalized for term in observable_terms):
            raise ValueError(
                f"Godot gameplay criteria must be observable 2D mechanics or rendered-state outcomes: {criterion}"
            )


def validate_godot_side_scroll_brief(brief: UserBrief) -> None:
    """Bind the side-scroll route to its exact deterministic evidence surface."""

    observable_terms = (
        "side", "horizontal", "right", "advance", "travel", "journey", "lane",
        "enemy", "spawn", "attack", "combat", "defeat", "kill", "destination",
        "progress", "victory", "visual", "render", "screen",
    )
    unsupported_terms = (
        "3d", "multiplayer", "network", "server", "backend", "plugin", "storefront",
        "jump", "platformer", "open world", "save game",
    )
    for criterion in brief.acceptance_criteria:
        normalized = " ".join(criterion.casefold().split())
        if any(term in normalized for term in unsupported_terms):
            raise ValueError(f"Godot side-scroll evidence cannot verify this criterion: {criterion}")
        if not any(term in normalized for term in observable_terms):
            raise ValueError(
                f"Godot side-scroll criteria must be observable horizontal mechanics or rendered outcomes: {criterion}"
            )


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
        "version": "0.6.0",
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
    work_mode: str,
    requested_toolpack_id: str | None = None,
    requested_toolpack_binding: ToolPackBinding | None = None,
    source_snapshot=None,
) -> dict[str, object]:
    selected = APPROVED_TOOLPACKS.select(
        project_kind=project_kind,
        work_mode=work_mode,
        requested_toolpack_id=requested_toolpack_id,
    )
    toolpack = APPROVED_TOOLPACKS.resolve(requested_toolpack_binding) if requested_toolpack_binding else selected
    if toolpack.binding() != selected.binding():
        raise PermissionError("the confirmed ToolPack binding is no longer the approved compatible route")
    binding = toolpack.binding()
    brief_updates = {
        "toolpack_binding": binding,
        "authorized_output_files": list(toolpack.manifest.output.authorized_paths),
    }
    if toolpack.manifest.toolpack_id == "godot.topology":
        validate_godot_topology_brief(brief)
        brief_updates["max_repairs_per_quest"] = 0
    elif toolpack.manifest.toolpack_id == "godot.visual-prototype":
        validate_godot_visual_brief(brief)
        brief_updates["max_repairs_per_quest"] = 0
    elif toolpack.manifest.toolpack_id == "godot.gameplay":
        validate_godot_gameplay_brief(brief)
        brief_updates["max_repairs_per_quest"] = 0
    elif toolpack.manifest.toolpack_id == "godot.side-scroll-experiment":
        validate_godot_side_scroll_brief(brief)
        brief_updates["max_repairs_per_quest"] = 0
    brief = brief.model_copy(update=brief_updates)
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
    record = record.model_copy(update={
        "cloud_project_id": str(dispatch.get("project_id", "")),
        "cloud_region": str(dispatch.get("region", "")),
        "cloud_job_name": str(dispatch.get("job_name", "")),
        "cloud_operation_name": str(dispatch.get("operation_name", "")),
    })
    store.update(record)
    payload = record.model_dump(mode="json")
    payload["telemetry"] = execution_telemetry(record)
    return {"record": payload, "dispatch": dispatch}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, identity: Annotated[Identity, Depends(require_identity)]) -> dict[str, object]:
    try:
        record = CloudRunStore().read_record(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    if record.owner_id != identity.owner_id:
        raise HTTPException(status_code=404, detail="run not found")
    payload = record.model_dump(mode="json")
    payload["telemetry"] = execution_telemetry(record)
    return payload


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


@app.get("/api/projects/{project_id}/source.zip")
def get_project_source(
    project_id: str,
    identity: Annotated[Identity, Depends(require_identity)],
) -> Response:
    """Return the owner-bound verified source ZIP for Browser or Godot results."""

    try:
        project = CloudProjectStore().read_owned(project_id, identity.owner_id)
        store = CloudRunStore()
        run = store.read_record(project.latest_run_id)
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
    if (
        project.latest_status != RunStatus.PASSED
        or run.status != RunStatus.PASSED
        or run.project_id != project.project_id
        or run.owner_id != identity.owner_id
    ):
        raise HTTPException(status_code=409, detail="project has no verified downloadable result")
    try:
        payload = store.read_source_archive(run.run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail="verified source archive is unavailable") from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="khalinos-{project.project_id}.zip"',
            "X-KHALINOS-Run-ID": run.run_id,
            "Cache-Control": "private, no-store",
        },
    )


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
        if request.requested_work_mode == "new_product_build":
            if request.selected_project_id or request.upload_id:
                raise ValueError("a new product cannot be bound to an existing project snapshot")
            if request.requested_project_kind not in {"browser", "godot"}:
                raise ValueError("choose an approved new-project runtime before SixSense")
        elif not request.selected_project_id and not request.upload_id:
            raise ValueError("existing-project repair requires a KHALINOS project or validated ZIP")
        try:
            selected_toolpack = APPROVED_TOOLPACKS.select(
                project_kind=request.requested_project_kind or "browser",
                work_mode=request.requested_work_mode,
                requested_toolpack_id=request.requested_toolpack_id,
            )
            if request.requested_toolpack_binding:
                bound_toolpack = APPROVED_TOOLPACKS.resolve(request.requested_toolpack_binding)
                if bound_toolpack.binding() != selected_toolpack.binding():
                    raise PermissionError("the confirmed ToolPack binding does not match the selected route")
        except PermissionError as exc:
            raise ValueError(str(exc)) from exc
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


@app.post("/api/routes/recommend")
async def recommend_route(
    request: RouteRecommendationRequest,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    """Rank only statically approved ToolPacks; this does not grant execution authority."""

    del identity
    inspection = inspect_materials(MaterialInspectionRequest(
        project_locator=request.project_locator,
        materials=request.materials,
    ))
    candidates = APPROVED_TOOLPACKS.routing_candidates(work_mode=request.requested_work_mode)
    if not candidates:
        raise HTTPException(status_code=422, detail="no approved ToolPack supports this work mode")
    try:
        recommendation = await RouteAdvisor().recommend(request, inspection, candidates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    manifests = {item.toolpack_id: item for item in candidates}
    return {
        "recommendation": recommendation.model_dump(mode="json"),
        "options": [
            {
                "toolpack": {
                    "toolpack_id": manifests[item.toolpack_id].toolpack_id,
                    "version": manifests[item.toolpack_id].version,
                    "display_name": manifests[item.toolpack_id].display_name,
                    "description": manifests[item.toolpack_id].description,
                    "manifest_sha256": manifests[item.toolpack_id].sha256(),
                },
                "project_kind": manifests[item.toolpack_id].routing.primary_project_kind,
                "assessment": item.model_dump(mode="json"),
            }
            for item in recommendation.candidates
        ],
    }


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


@app.post("/api/intakes/{intake_id}/reroute", status_code=201)
async def reroute_ready_intake(
    intake_id: str,
    reroute: IntakeReroute,
    identity: Annotated[Identity, Depends(require_identity)],
) -> dict[str, object]:
    store = CloudIntakeStore()
    try:
        previous = store.read(intake_id)
        if previous.owner_id != identity.owner_id:
            raise FileNotFoundError(intake_id)
        if previous.requested_work_mode != "new_product_build":
            raise ValueError("route changes are available only for new-product builds")
        selected = APPROVED_TOOLPACKS.select(
            project_kind=reroute.requested_project_kind,
            work_mode=previous.requested_work_mode,
            requested_toolpack_id=reroute.requested_toolpack_id,
        )
        bound = APPROVED_TOOLPACKS.resolve(reroute.requested_toolpack_binding)
        if selected.binding() != bound.binding():
            raise ValueError("the confirmed ToolPack binding does not match the selected route")
        record = await reroute_intake(
            intake_id,
            reroute,
            store=store,
            agent=SixSenseAgent(),
        )
        return record.model_dump(mode="json")
    except (FileNotFoundError, PermissionError) as exc:
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
        work_mode = "existing_project_repair"
    else:
        created_at = intake.created_at
        origin = "external" if intake.material_inspection and intake.material_inspection.source_available else "khalinos"
        work_mode = intake.requested_work_mode
        if work_mode == "new_product_build":
            if intake.requested_project_kind not in {"browser", "godot"}:
                raise HTTPException(status_code=409, detail="the intake has no approved new-project runtime")
            project_kind = intake.requested_project_kind
        else:
            if intake.source_snapshot is None:
                raise HTTPException(status_code=409, detail="existing-project repair requires a verified source snapshot")
            detected_kind = intake.material_inspection.project_kind if intake.material_inspection else "unknown"
            project_kind = detected_kind if detected_kind in {"godot", "unity", "web"} else "browser"
    requested_toolpack_id = (
        intake.requested_toolpack_binding.toolpack_id
        if intake.requested_toolpack_binding is not None
        else intake.requested_toolpack_id
    )
    try:
        result = queue_run(
            authorized_brief(
                intake.preview,
                include_preview_quality=(
                    project_kind != "godot" or requested_toolpack_id in {
                        "godot.visual-prototype", "godot.gameplay", "godot.side-scroll-experiment",
                    }
                ),
                authoritative_sources=source_payloads(store, intake),
            ),
            owner_id=identity.owner_id,
            project_id=project_id,
            project_kind=project_kind,
            work_mode=work_mode,
            requested_toolpack_id=intake.requested_toolpack_id,
            requested_toolpack_binding=intake.requested_toolpack_binding,
            source_snapshot=intake.source_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
