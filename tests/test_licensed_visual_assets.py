from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

import khalinos.licensed_visual_assets as licensed
from khalinos.licensed_visual_assets import (
    LICENSED_ATLAS_PATH,
    build_licensed_art_bundle,
    grade_asset_library,
    grading_manifest,
)
from khalinos.agent_capability_receipts import build_agent_capability_trace
from khalinos.godot_side_scroll import (
    GODOT_SIDE_SCROLL_LICENSED_ART_PROFILE,
    compile_godot_side_scroll,
    compose_godot_side_scroll_capabilities,
)
from khalinos.models import canonical_sha256


def _write_sprite(path: Path, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = ((seed * 53) % 255, (seed * 97) % 255, (seed * 151) % 255, 255)
    for index in range(18):
        inset = 32 + index * 7
        draw.rectangle((inset, inset, 511 - inset, 511 - inset), outline=color, width=3)
    draw.polygon(((256, 44), (430, 430), (82, 430)), fill=color)
    image.save(path, format="PNG")


def _library(root: Path, monkeypatch) -> None:
    paths = sorted({
        relative
        for roles in licensed._CURATED_ROLE_PATHS.values()
        for relative in roles.values()
    })
    paths.extend((
        "32px/characters/08ce32d2-0000-0000-0000-000000000000.png",
        "32px/props/ffffffff-0000-0000-0000-000000000000.png",
    ))
    monkeypatch.setattr(licensed, "EXPECTED_CATALOG_SIZE", len(paths))
    for index, relative in enumerate(paths):
        _write_sprite(root / relative, index + 1)


def test_library_grading_preserves_all_assets_and_binds_only_grade_a(tmp_path: Path, monkeypatch) -> None:
    _library(tmp_path, monkeypatch)
    entries = grade_asset_library(tmp_path)
    manifest = grading_manifest(entries)

    assert manifest["grade_counts"] == {"A": 13, "B": 1, "C": 1}
    assert manifest["total_assets"] == len(entries)
    assert all(item.source_url.endswith(item.relative_path.rsplit("/", 1)[-1]) for item in entries)
    assert all(not item.selected_roles for item in entries if item.grade != "A")


def test_profile_bundles_are_deterministic_and_license_bound(tmp_path: Path, monkeypatch) -> None:
    _library(tmp_path, monkeypatch)

    trinity = build_licensed_art_bundle(tmp_path, "godot.trinity-top-down")
    trinity_repeat = build_licensed_art_bundle(tmp_path, "godot.trinity-top-down")
    side = build_licensed_art_bundle(tmp_path, "godot.side-scroll-destination")

    assert trinity.atlas.path == side.atlas.path == LICENSED_ATLAS_PATH
    assert trinity.atlas.sha256 == trinity_repeat.atlas.sha256
    assert len(trinity.selected_assets) == 8
    assert len(side.selected_assets) == 13
    assert trinity.atlas.sha256 != side.atlas.sha256
    assert trinity.license_receipt["passed"] is True
    assert trinity.license_receipt["standalone_asset_pack_redistribution_allowed"] is False
    assert trinity.license_receipt["output_atlas_sha256"] == trinity.atlas.sha256
    assert set(trinity.text_files()) == {
        licensed.ASSET_SELECTION_PATH,
        licensed.STYLE_COMPOSITION_PATH,
        licensed.LICENSED_ATLAS_MANIFEST_PATH,
        licensed.LICENSE_RECEIPT_PATH,
    }


def test_side_scroll_binds_the_license_chain_to_existing_visual_agents(
    tmp_path: Path, monkeypatch
) -> None:
    _library(tmp_path, monkeypatch)
    bundle = build_licensed_art_bundle(tmp_path, "godot.side-scroll-destination")
    namespace = __import__("runpy").run_path(
        str(Path(__file__).with_name("test_godot_side_scroll.py"))
    )
    base = namespace["side_scroll_artifact"]()
    artifact = compile_godot_side_scroll(
        base.plan, base.concept, base.asset, bundle
    )
    composition = compose_godot_side_scroll_capabilities(base.plan, bundle)
    trace = build_agent_capability_trace(
        profile_id="godot.side-scroll-destination",
        plan_sha256=artifact.plan_sha256,
        artifact_bundle_sha256=artifact.bundle_sha256,
        evidence_sha256=canonical_sha256({"licensed_runtime": "PASS"}),
        composition=composition,
        profile=GODOT_SIDE_SCROLL_LICENSED_ART_PROFILE,
        binary_sha256_by_path={
            artifact.asset.path: artifact.asset.sha256,
            bundle.atlas.path: bundle.atlas.sha256,
        },
    )
    visual = next(
        item for item in trace.receipts
        if item.agent_id == "khalinos_visual_candidate_maker"
    )
    assert tuple(item.pack_id for item in visual.capability_pack_bindings) == (
        "godot.visual-foundation",
        "godot.asset-selector",
        "godot.style-composer",
        "godot.licensed-atlas",
        "godot.license-receipt",
    )
    assert trace.max_agent_slots == 13
    assert "khalinos_sprite_atlas_verifier" not in trace.active_agent_ids
