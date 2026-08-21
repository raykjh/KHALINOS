from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from khalinos.godot_gameplay import GODOT_GAMEPLAY_BASE_PROFILE
from khalinos.godot_side_scroll import (
    GODOT_SIDE_SCROLL_PROFILE,
    CompiledGodotSideScroll,
    GodotSideScrollPlan,
    compile_godot_side_scroll,
    compose_godot_side_scroll_capabilities,
)
from khalinos.godot_side_scroll_toolpack import GODOT_SIDE_SCROLL_TOOLPACK
from khalinos.models import VisualConcept
from khalinos.visual_assets import trusted_png_asset


def background_png() -> bytes:
    image = Image.new("RGB", (960, 540), "#bde6ef")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 310, 960, 540), fill="#d6c58b")
    for x in range(0, 960, 120):
        draw.ellipse((x - 40, 220, x + 90, 360), fill="#79aa68")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def side_scroll_artifact() -> CompiledGodotSideScroll:
    plan = GodotSideScrollPlan(project_name="Trinity Roadbound")
    concept = VisualConcept(
        candidate_id="V1",
        name="Sunlit Roadbound",
        design_thesis="A bright horizontal road makes forward travel and approaching green enemies immediately readable.",
        composition="The party anchors the left third while enemies and the destination occupy the travel lane to the right.",
        typography="Compact dark HUD labels remain legible against the bright landscape.",
        palette=["sky", "sand", "leaf"],
        interaction_emphasis="Travel progress, automatic attacks, enemies, and the destination flag dominate the frame.",
        anti_goals=["top-down arena", "static dashboard"],
    )
    return compile_godot_side_scroll(plan, concept, trusted_png_asset(background_png()))


def test_side_scroll_reuses_common_packs_but_replaces_the_genre_chain() -> None:
    assert GODOT_SIDE_SCROLL_PROFILE[:2] == GODOT_GAMEPLAY_BASE_PROFILE[:2]
    assert tuple(pack.pack_id for pack in GODOT_SIDE_SCROLL_PROFILE) == (
        "godot.project-core",
        "godot.visual-foundation",
        "godot.side-scroll-lane-combat",
        "godot.destination-progression",
        "godot.side-scroll-probe",
    )
    assert set(pack.pack_id for pack in GODOT_SIDE_SCROLL_PROFILE[2:]).isdisjoint(
        pack.pack_id for pack in GODOT_GAMEPLAY_BASE_PROFILE[2:]
    )


def test_side_scroll_compiler_is_deterministic_and_owns_exact_outputs(tmp_path: Path) -> None:
    first = side_scroll_artifact()
    second = side_scroll_artifact()
    assert first.bundle_sha256 == second.bundle_sha256
    composition = compose_godot_side_scroll_capabilities(first.plan)
    assert tuple(binding.pack_id for binding in composition.bindings) == tuple(
        pack.pack_id for pack in GODOT_SIDE_SCROLL_PROFILE
    )
    assert set(composition.text_files) == set(first.files)
    assert composition.binary_paths == (first.asset.path,)
    destination = tmp_path / "product"
    GODOT_SIDE_SCROLL_TOOLPACK.execution_adapter.materialize(first, destination)
    assert {path.as_posix() for path in destination.rglob("*") if path.is_file()} == {
        (destination / path).as_posix() for path in [*first.files, first.asset.path]
    }


def test_side_scroll_materializer_refuses_changed_approved_output(tmp_path: Path) -> None:
    artifact = side_scroll_artifact()
    changed = artifact.model_copy(update={
        "files": {**artifact.files, "scripts/khalinos_side_scroll.gd": "extends Node\n"},
    })
    with pytest.raises(PermissionError, match="bundle digest changed"):
        GODOT_SIDE_SCROLL_TOOLPACK.execution_adapter.materialize(changed, tmp_path / "product")


def test_real_godot_side_scroll_probe_and_render(tmp_path: Path, monkeypatch) -> None:
    executable = r"E:\memory R data\archive_20260818_first_priority\C-tmp\khalinos-engine-bakeoff\godot\Godot_v4.7.1-stable_win64.exe"
    monkeypatch.setenv("KHALINOS_GODOT_EXECUTABLE", executable)
    artifact = side_scroll_artifact()
    product = tmp_path / "product"
    evidence = tmp_path / "evidence"
    GODOT_SIDE_SCROLL_TOOLPACK.execution_adapter.materialize(artifact, product)
    receipt = GODOT_SIDE_SCROLL_TOOLPACK.evidence_adapter.verify(
        artifact,
        product,
        evidence,
        ["The party advances right, defeats enemies automatically, and reaches the destination."],
    )
    assert receipt.passed is True
    assert all(receipt.checks.values())
    assert (evidence / "side-scroll-probe.json").is_file()
    assert receipt.screenshot_names
