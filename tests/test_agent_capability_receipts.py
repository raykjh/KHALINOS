from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

import pytest

from khalinos.agent_capability_receipts import (
    KHALINOS_AGENT_SLOT_IDS,
    KHALINOS_MAX_AGENT_SLOTS,
    build_agent_capability_trace,
    compare_agent_capability_traces,
)
from khalinos.agents import AgentTeam
from khalinos.godot_gameplay import (
    GODOT_GAMEPLAY_SPRITE_PROFILE,
    compose_godot_gameplay_capabilities,
)
from khalinos.godot_side_scroll import (
    GODOT_SIDE_SCROLL_PROFILE,
    compose_godot_side_scroll_capabilities,
)


def _fixture_function(filename: str, name: str):
    namespace = runpy.run_path(str(Path(__file__).with_name(filename)))
    return namespace[name]


def _sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _pack_ids(trace, agent_id: str) -> tuple[str, ...]:
    receipt = next(item for item in trace.receipts if item.agent_id == agent_id)
    return tuple(binding.pack_id for binding in receipt.capability_pack_bindings)


def test_receipt_inventory_matches_the_existing_fixed_agent_team() -> None:
    team = AgentTeam()
    configured = tuple(sorted(
        value.name
        for value in vars(team).values()
        if getattr(value, "name", "").startswith("khalinos_")
    ))
    assert configured == KHALINOS_AGENT_SLOT_IDS
    assert KHALINOS_MAX_AGENT_SLOTS == 13


def test_trinity_and_side_scroll_rebind_existing_slots_without_creating_agents() -> None:
    trinity = _fixture_function("test_godot_gameplay_toolpack.py", "artifact")()
    side_scroll = _fixture_function("test_godot_side_scroll.py", "side_scroll_artifact")()
    trinity_composition = compose_godot_gameplay_capabilities(
        trinity.gameplay, trinity.sprite_plan
    )
    side_composition = compose_godot_side_scroll_capabilities(side_scroll.plan)
    trinity_trace = build_agent_capability_trace(
        profile_id="godot.trinity-top-down",
        plan_sha256=trinity.plan_sha256,
        artifact_bundle_sha256=trinity.bundle_sha256,
        evidence_sha256=_sha256({"fixture": "trinity-runtime-pass"}),
        composition=trinity_composition,
        profile=GODOT_GAMEPLAY_SPRITE_PROFILE,
        binary_sha256_by_path={
            trinity.asset.path: trinity.asset.sha256,
            trinity.sprite_atlas.path: trinity.sprite_atlas.sha256,
        },
    )
    side_trace = build_agent_capability_trace(
        profile_id="godot.side-scroll-destination",
        plan_sha256=side_scroll.plan_sha256,
        artifact_bundle_sha256=side_scroll.bundle_sha256,
        evidence_sha256=_sha256({"fixture": "side-scroll-runtime-pass"}),
        composition=side_composition,
        profile=GODOT_SIDE_SCROLL_PROFILE,
        binary_sha256_by_path={side_scroll.asset.path: side_scroll.asset.sha256},
    )

    assert trinity_trace.max_agent_slots == side_trace.max_agent_slots == 13
    assert len(trinity_trace.active_agent_ids) == 9
    assert len(side_trace.active_agent_ids) == 8
    assert set(side_trace.active_agent_ids) < set(trinity_trace.active_agent_ids)
    assert set(trinity_trace.active_agent_ids) - set(side_trace.active_agent_ids) == {
        "khalinos_sprite_atlas_verifier"
    }
    assert _pack_ids(trinity_trace, "khalinos_accountable_maker") == (
        "godot.project-core",
        "godot.top-down-auto-combat",
        "godot.combat-feedback",
        "godot.presentation-skin",
        "godot.audio-feedback",
    )
    assert _pack_ids(side_trace, "khalinos_accountable_maker") == (
        "godot.project-core",
        "godot.side-scroll-lane-combat",
        "godot.combat-feedback",
        "godot.presentation-skin",
        "godot.audio-feedback",
        "godot.destination-progression",
    )
    assert _pack_ids(trinity_trace, "khalinos_godot_independent_verifier") == (
        "godot.gameplay-probe",
    )
    assert _pack_ids(side_trace, "khalinos_godot_independent_verifier") == (
        "godot.side-scroll-probe",
    )
    assert all(not receipt.model_invoked and receipt.model_calls == 0 for receipt in trinity_trace.receipts)
    assert all(not receipt.model_invoked and receipt.model_calls == 0 for receipt in side_trace.receipts)
    assert trinity_trace.sha256() != side_trace.sha256()
    comparison = compare_agent_capability_traces(trinity_trace, side_trace)
    assert comparison["fixed_max_agent_slots"] == 13
    assert comparison["new_agent_slots_created"] is False
    assert comparison["only_in_first"] == ["khalinos_sprite_atlas_verifier"]
    assert comparison["only_in_second"] == []
    assert comparison["pack_changes_by_agent"]["khalinos_accountable_maker"]["changed"] is True
    assert comparison["model_calls_recorded"] == 0
    assert comparison["model_agent_slots_invoked"] == []

    cloud_side_trace = build_agent_capability_trace(
        profile_id="godot.side-scroll-destination",
        plan_sha256=side_scroll.plan_sha256,
        artifact_bundle_sha256=side_scroll.bundle_sha256,
        evidence_sha256=_sha256({"fixture": "side-scroll-cloud-pass"}),
        composition=side_composition,
        profile=GODOT_SIDE_SCROLL_PROFILE,
        binary_sha256_by_path={side_scroll.asset.path: side_scroll.asset.sha256},
        model_calls_by_agent={
            "khalinos_godot_quest_owner": 1,
            "khalinos_godot_gameplay_owner": 1,
            "khalinos_visual_candidate_maker": 3,
        },
    )
    assert cloud_side_trace.execution_scope == "cloud_workflow_execution"
    cloud_comparison = compare_agent_capability_traces(cloud_side_trace, cloud_side_trace)
    assert cloud_comparison["model_calls_recorded"] == 10
    assert cloud_comparison["model_agent_slots_invoked"] == [
        "khalinos_godot_gameplay_owner",
        "khalinos_godot_quest_owner",
        "khalinos_visual_candidate_maker",
    ]
    assert "actual model-agent invocations" in cloud_comparison["scope_note"]


def test_trace_rejects_a_profile_that_does_not_match_the_executed_composition() -> None:
    side_scroll = _fixture_function("test_godot_side_scroll.py", "side_scroll_artifact")()
    composition = compose_godot_side_scroll_capabilities(side_scroll.plan)
    with pytest.raises(PermissionError, match="do not match"):
        build_agent_capability_trace(
            profile_id="godot.side-scroll-destination",
            plan_sha256=side_scroll.plan_sha256,
            artifact_bundle_sha256=side_scroll.bundle_sha256,
            evidence_sha256=_sha256({"fixture": "side-scroll-runtime-pass"}),
            composition=composition,
            profile=tuple(reversed(GODOT_SIDE_SCROLL_PROFILE)),
            binary_sha256_by_path={side_scroll.asset.path: side_scroll.asset.sha256},
        )
