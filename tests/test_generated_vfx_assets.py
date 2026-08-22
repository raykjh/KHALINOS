from __future__ import annotations

from khalinos.generated_vfx_assets import (
    EFFECT_ATLAS_PATH,
    EFFECT_ATLAS_MANIFEST_PATH,
    EFFECT_RECEIPT_PATH,
    EFFECT_SELECTION_PATH,
    build_effect_bundle,
)
from pathlib import Path
import runpy

from khalinos.agent_capability_receipts import build_agent_capability_trace
from khalinos.godot_side_scroll import (
    GODOT_SIDE_SCROLL_VFX_PROFILE,
    compile_godot_side_scroll,
    compose_godot_side_scroll_capabilities,
)
from khalinos.models import canonical_sha256


def test_generated_effect_atlas_is_deterministic_and_receipt_bound() -> None:
    first = build_effect_bundle("godot.trinity-top-down")
    second = build_effect_bundle("godot.trinity-top-down")

    assert first.atlas.path == EFFECT_ATLAS_PATH
    assert first.atlas.sha256 == second.atlas.sha256
    assert (first.atlas.width, first.atlas.height) == (1728, 768)
    assert [item["role"] for item in first.atlas_manifest["slots"]] == [
        "warrior_slash",
        "archer_impact",
        "healer_restoration",
        "enemy_claw",
    ]
    assert all(item["frames"] == 9 for item in first.atlas_manifest["slots"])
    assert first.receipt["passed"] is True
    assert first.receipt["output_atlas_sha256"] == first.atlas.sha256
    assert first.receipt["external_stock_asset_license_required"] is False
    assert set(first.text_files()) == {
        EFFECT_SELECTION_PATH,
        EFFECT_ATLAS_MANIFEST_PATH,
        EFFECT_RECEIPT_PATH,
    }


def test_both_profiles_share_exact_effect_bytes_but_keep_distinct_receipts() -> None:
    trinity = build_effect_bundle("godot.trinity-top-down")
    side = build_effect_bundle("godot.side-scroll-destination")

    assert trinity.atlas.sha256 == side.atlas.sha256
    assert trinity.selection_manifest["profile_id"] != side.selection_manifest["profile_id"]
    assert trinity.receipt["profile_id"] != side.receipt["profile_id"]


def test_effect_chain_is_visible_in_the_existing_visual_agent_receipt() -> None:
    namespace = runpy.run_path(str(Path(__file__).with_name("test_godot_side_scroll.py")))
    base = namespace["side_scroll_artifact"]()
    effects = build_effect_bundle("godot.side-scroll-destination")
    artifact = compile_godot_side_scroll(
        base.plan, base.concept, base.asset, effects=effects
    )
    composition = compose_godot_side_scroll_capabilities(
        base.plan, effects=effects
    )
    trace = build_agent_capability_trace(
        profile_id="godot.side-scroll-destination",
        plan_sha256=artifact.plan_sha256,
        artifact_bundle_sha256=artifact.bundle_sha256,
        evidence_sha256=canonical_sha256({"effect_runtime": "PASS"}),
        composition=composition,
        profile=GODOT_SIDE_SCROLL_VFX_PROFILE,
        binary_sha256_by_path={
            artifact.asset.path: artifact.asset.sha256,
            effects.atlas.path: effects.atlas.sha256,
        },
    )
    visual = next(
        item for item in trace.receipts
        if item.agent_id == "khalinos_visual_candidate_maker"
    )
    assert tuple(item.pack_id for item in visual.capability_pack_bindings) == (
        "godot.visual-foundation",
        "godot.effect-selector",
        "godot.effect-atlas",
        "godot.vfx-player",
        "godot.effect-receipt",
    )
    assert trace.max_agent_slots == 13
