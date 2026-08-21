"""Explicit application-level dispatch to approved ToolPack workflows."""

from __future__ import annotations

from khalinos.godot_workflow import execute_godot_run
from khalinos.godot_visual_workflow import execute_godot_visual_run
from khalinos.godot_gameplay_workflow import execute_godot_gameplay_run
from khalinos.models import RunRecord, RunStatus, canonical_sha256
from khalinos.projects import ProjectStore
from khalinos.storage import RunStore
from khalinos.toolpacks import ToolPackRegistry
from khalinos.workflow import Team, execute_run


async def execute_authorized_run(
    run_id: str,
    *,
    store: RunStore,
    team: Team,
    registry: ToolPackRegistry,
    project_store: ProjectStore | None = None,
) -> RunRecord:
    record = store.read_record(run_id)
    if record.status != RunStatus.QUEUED:
        return record
    claimed = store.claim_execution(run_id)
    if claimed is None:
        return store.read_record(run_id)
    record = claimed
    brief = store.read_brief(run_id)
    binding = brief.toolpack_binding
    if binding is None or binding != record.toolpack_binding:
        failed = record.model_copy(update={
            "status": RunStatus.FAILED,
            "message": "PermissionError: run and approved brief must carry the same ToolPack binding",
        })
        store.update(failed)
        return failed
    if canonical_sha256(brief) != record.brief_sha256:
        failed = record.model_copy(update={
            "status": RunStatus.FAILED,
            "message": "PermissionError: approved brief digest changed after authorization",
        })
        store.update(failed)
        return failed
    try:
        toolpack = registry.resolve(binding)
    except PermissionError as exc:
        failed = record.model_copy(update={
            "status": RunStatus.FAILED,
            "message": f"PermissionError: {exc}"[:1000],
        })
        store.update(failed)
        return failed
    if toolpack.manifest.toolpack_id == "browser.product":
        return await execute_run(
            run_id,
            store=store,
            team=team,
            registry=registry,
            project_store=project_store,
        )
    if toolpack.manifest.toolpack_id == "godot.topology":
        return await execute_godot_run(
            run_id,
            store=store,
            team=team,
            registry=registry,
            project_store=project_store,
        )
    if toolpack.manifest.toolpack_id == "godot.visual-prototype":
        return await execute_godot_visual_run(
            run_id,
            store=store,
            team=team,
            registry=registry,
            project_store=project_store,
        )
    if toolpack.manifest.toolpack_id == "godot.gameplay":
        return await execute_godot_gameplay_run(
            run_id,
            store=store,
            team=team,
            registry=registry,
            project_store=project_store,
        )
    failed = record.model_copy(update={
        "status": RunStatus.FAILED,
        "message": f"PermissionError: no workflow is approved for {toolpack.manifest.toolpack_id}",
    })
    store.update(failed)
    return failed
