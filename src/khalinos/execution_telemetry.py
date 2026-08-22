"""Truthful presentation metadata derived from persisted workflow state."""

from __future__ import annotations

from typing import Any

from khalinos.models import RunRecord, RunStatus


PROFILE_BY_TOOLPACK: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "godot.gameplay": (
        "godot.trinity-top-down",
        "Trinity top-down survival",
        (
            "godot.project-core",
            "godot.visual-foundation",
            "godot.top-down-auto-combat",
            "godot.combat-feedback",
            "godot.gameplay-probe",
            "godot.sprite-atlas",
        ),
    ),
    "godot.side-scroll-experiment": (
        "godot.side-scroll-destination",
        "Side-scroll destination",
        (
            "godot.project-core",
            "godot.visual-foundation",
            "godot.side-scroll-lane-combat",
            "godot.combat-feedback",
            "godot.destination-progression",
            "godot.side-scroll-probe",
        ),
    ),
    "godot.visual-prototype": (
        "godot.visual-prototype",
        "Godot visual prototype",
        ("godot.project-core", "godot.visual-foundation"),
    ),
    "godot.topology": (
        "godot.topology",
        "Godot topology repair",
        ("godot.topology",),
    ),
    "browser.product": (
        "browser.product",
        "Browser product",
        ("browser.product",),
    ),
}


STAGES = (
    ("authority", "01 Authority"),
    ("orchestration", "02 Orchestration"),
    ("production", "03 Production"),
    ("evidence", "04 Evidence gates"),
    ("result", "05 Result"),
)


def _stage(record: RunRecord) -> str:
    status = record.status
    if status in {RunStatus.QUEUED, RunStatus.PLANNING}:
        return "orchestration"
    if status in {RunStatus.VISUALIZING, RunStatus.VISUAL_SELECTING, RunStatus.EXECUTING}:
        return "production"
    if status == RunStatus.RUNTIME_CHECKING and "candidate" in record.message.lower():
        return "production"
    if status in {RunStatus.RUNTIME_CHECKING, RunStatus.VERIFYING, RunStatus.REPAIRING, RunStatus.BLOCKED}:
        return "evidence"
    return "result"


def _actor(record: RunRecord, toolpack_id: str) -> dict[str, str]:
    status = record.status
    message = record.message.lower()
    if status == RunStatus.QUEUED:
        return {"id": "cloud_run_service", "label": "Cloud Run Service", "kind": "CLOUD RUNTIME"}
    if status == RunStatus.PLANNING:
        agent_id = "khalinos_godot_gameplay_owner" if toolpack_id in {"godot.gameplay", "godot.side-scroll-experiment"} else "khalinos_project_owner"
        return {"id": agent_id, "label": "Gemini Project Owner", "kind": "MODEL AGENT"}
    if status == RunStatus.VISUALIZING:
        if "nano banana" in message or "candidate" in message:
            return {"id": "khalinos_visual_candidate_maker", "label": "Visual Candidate Maker", "kind": "MODEL SERVICE"}
        return {"id": "khalinos_visual_director", "label": "Visual Director", "kind": "MODEL AGENT"}
    if status == RunStatus.VISUAL_SELECTING:
        return {"id": "khalinos_visual_verifier", "label": "Visual Verifier", "kind": "MODEL AGENT"}
    if status == RunStatus.EXECUTING:
        if record.work_mode == "existing_project_repair":
            return {"id": "khalinos_technical_repair", "label": "Technical Repair", "kind": "MODEL AGENT"}
        kind = "TRUSTED HOST" if toolpack_id.startswith("godot.") else "MODEL AGENT"
        return {"id": "khalinos_accountable_maker", "label": "Accountable Maker", "kind": kind}
    if status == RunStatus.RUNTIME_CHECKING:
        return {"id": "khalinos_deterministic_runtime", "label": "Deterministic Runtime", "kind": "TRUSTED HOST"}
    if status == RunStatus.VERIFYING:
        return {"id": "khalinos_independent_verifier", "label": "Role-separated Verifier", "kind": "MODEL AGENT"}
    if status == RunStatus.REPAIRING:
        return {"id": "khalinos_technical_repair", "label": "Technical Repair", "kind": "MODEL AGENT"}
    if status == RunStatus.PASSED:
        return {"id": "verified_result", "label": "Verified Result", "kind": "DIGEST-BOUND"}
    return {"id": "safe_stop", "label": "Safe Stop", "kind": "EVIDENCE BOUNDARY"}


def _active_packs(toolpack_id: str, actor_id: str, all_packs: tuple[str, ...]) -> list[str]:
    if actor_id in {"cloud_run_service", "verified_result", "safe_stop"}:
        return []
    if "visual" in actor_id:
        return [item for item in all_packs if item in {"godot.visual-foundation", "godot.sprite-atlas"}]
    if actor_id == "khalinos_accountable_maker":
        return [item for item in all_packs if item not in {"godot.visual-foundation", "godot.gameplay-probe", "godot.side-scroll-probe", "godot.sprite-atlas"}]
    if actor_id in {"khalinos_deterministic_runtime", "khalinos_independent_verifier"}:
        probes = [item for item in all_packs if item.endswith("-probe")]
        return probes or ([toolpack_id] if toolpack_id else [])
    return list(all_packs)


def _milestones(record: RunRecord) -> list[dict[str, str]]:
    status = record.status
    order = {
        RunStatus.QUEUED: 1,
        RunStatus.PLANNING: 1,
        RunStatus.VISUALIZING: 2,
        RunStatus.VISUAL_SELECTING: 2,
        RunStatus.EXECUTING: 2,
        RunStatus.RUNTIME_CHECKING: 2 if "candidate" in record.message.lower() else 3,
        RunStatus.VERIFYING: 4,
        RunStatus.REPAIRING: 3,
        RunStatus.PASSED: 6,
        RunStatus.BLOCKED: 4,
        # A generic failure can be raised from any workflow phase. Without a
        # persisted phase-specific receipt, stop at orchestration rather than
        # visually claiming later milestones completed.
        RunStatus.FAILED: 1,
    }[status]
    labels = (
        ("M01", "Contract"),
        ("M02", "Plan"),
        ("M03", "Production"),
        ("M04", "Runtime"),
        ("M05", "Verification"),
        ("M06", "Delivery"),
    )
    result = []
    for index, (milestone_id, label) in enumerate(labels):
        if status == RunStatus.PASSED:
            state = "complete"
        elif status in {RunStatus.BLOCKED, RunStatus.FAILED} and index >= order:
            state = "stopped" if index == order else "pending"
        elif index < order:
            state = "complete"
        elif index == order:
            state = "active"
        else:
            state = "pending"
        result.append({"id": milestone_id, "label": label, "state": state})
    return result


def execution_telemetry(record: RunRecord) -> dict[str, Any]:
    """Return UI metadata that never claims more progress than the persisted run record."""

    toolpack_id = record.toolpack_binding.toolpack_id if record.toolpack_binding else ""
    profile_id, profile_label, packs = PROFILE_BY_TOOLPACK.get(
        toolpack_id,
        (toolpack_id or "unbound", toolpack_id or "Unbound route", (toolpack_id,) if toolpack_id else ()),
    )
    stage_id = _stage(record)
    stage_index = next(index for index, item in enumerate(STAGES) if item[0] == stage_id)
    actor = _actor(record, toolpack_id)
    return {
        "profile": {"id": profile_id, "label": profile_label},
        "capability_packs": list(packs),
        "active_capability_packs": _active_packs(toolpack_id, actor["id"], packs),
        "active_actor": actor,
        "stage": {"id": stage_id, "label": STAGES[stage_index][1], "index": stage_index},
        "stages": [{"id": item[0], "label": item[1]} for item in STAGES],
        "milestones": _milestones(record),
        "verifier_state": (
            "active" if record.status == RunStatus.VERIFYING else
            "passed" if record.status == RunStatus.PASSED else
            "stopped" if record.status in {RunStatus.BLOCKED, RunStatus.FAILED} else
            "waiting"
        ),
        "receipt_count": len(record.completed_receipt_ids),
        "cloud": {
            "project_id": record.cloud_project_id,
            "region": record.cloud_region,
            "job_name": record.cloud_job_name,
            "operation_name": record.cloud_operation_name,
            "execution_id": record.cloud_execution_id,
        },
    }
