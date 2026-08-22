from __future__ import annotations

from khalinos.execution_telemetry import execution_telemetry
from khalinos.models import RunRecord, RunStatus
from khalinos.toolpacks import ToolPackBinding


def record(status: RunStatus, *, message: str = "Working.") -> RunRecord:
    return RunRecord(
        run_id="a" * 32,
        status=status,
        brief_sha256="b" * 64,
        toolpack_binding=ToolPackBinding(
            toolpack_id="godot.side-scroll-experiment",
            version="0.4.0",
            manifest_sha256="c" * 64,
        ),
        message=message,
        cloud_project_id="khalinos-agent-20260818",
        cloud_region="asia-northeast3",
        cloud_job_name="khalinos-worker",
        cloud_execution_id="khalinos-worker-demo",
    )


def test_side_scroll_production_exposes_real_profile_actor_and_pack_subset() -> None:
    telemetry = execution_telemetry(record(RunStatus.EXECUTING))

    assert telemetry["profile"]["id"] == "godot.side-scroll-destination"
    assert telemetry["stage"]["id"] == "production"
    assert telemetry["active_actor"]["id"] == "khalinos_accountable_maker"
    assert telemetry["active_capability_packs"] == [
        "godot.project-core",
        "godot.side-scroll-lane-combat",
        "godot.combat-feedback",
        "godot.presentation-skin",
        "godot.audio-feedback",
        "godot.destination-progression",
    ]
    assert [item["state"] for item in telemetry["milestones"]] == [
        "complete", "complete", "active", "pending", "pending", "pending"
    ]


def test_visual_candidate_message_selects_candidate_maker_without_claiming_runtime() -> None:
    telemetry = execution_telemetry(record(
        RunStatus.VISUALIZING,
        message="Nano Banana is generating side-scroll candidate V2.",
    ))

    assert telemetry["active_actor"]["id"] == "khalinos_visual_candidate_maker"
    assert telemetry["active_capability_packs"] == ["godot.visual-foundation"]
    assert telemetry["verifier_state"] == "waiting"


def test_candidate_runtime_remains_inside_production_milestone() -> None:
    telemetry = execution_telemetry(record(
        RunStatus.RUNTIME_CHECKING,
        message="Deterministic Runtime is checking real mechanics for side-scroll candidate V2.",
    ))

    assert telemetry["stage"]["id"] == "production"
    assert [item["state"] for item in telemetry["milestones"]] == [
        "complete", "complete", "active", "pending", "pending", "pending"
    ]


def test_passed_run_carries_every_milestone_and_cloud_identity() -> None:
    telemetry = execution_telemetry(record(RunStatus.PASSED))

    assert all(item["state"] == "complete" for item in telemetry["milestones"])
    assert telemetry["verifier_state"] == "passed"
    assert telemetry["cloud"] == {
        "project_id": "khalinos-agent-20260818",
        "region": "asia-northeast3",
        "job_name": "khalinos-worker",
        "operation_name": "",
        "execution_id": "khalinos-worker-demo",
    }
