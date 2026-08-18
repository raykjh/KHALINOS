from __future__ import annotations

import hashlib
import struct
import zlib

import pytest

from khalinos.godot_topology import GodotRegion, GodotTopologyPlan
from khalinos.godot_visual import CompiledGodotVisualPrototype, compile_godot_visual_prototype
from khalinos.godot_visual_toolpack import GODOT_VISUAL_PROTOTYPE_TOOLPACK
from khalinos.models import VisualConcept
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.visual_assets import trusted_png_asset


def png(width: int = 256, height: int = 256) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    rows = b"".join(
        b"\x00" + b"".join(bytes((x % 256, y % 256, (x + y) % 256, 255)) for x in range(width))
        for y in range(height)
    )
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def artifact() -> CompiledGodotVisualPrototype:
    topology = GodotTopologyPlan(
        project_name="Visual Passage",
        initial_region="entry",
        regions=(
            GodotRegion(region_id="entry", label="Entry", transitions=("route",)),
            GodotRegion(region_id="route", label="Route"),
        ),
    )
    concept = VisualConcept(
        candidate_id="V1",
        name="Carved Passage",
        design_thesis="A restrained ancient passage gives the decision screen a strong physical identity.",
        composition="A left-aligned route panel sits against a broad atmospheric environmental field.",
        typography="Large condensed headings pair with compact highly readable route labels.",
        palette=["charcoal", "sandstone", "oxidized copper"],
        interaction_emphasis="The active route remains the brightest and most legible element in the scene.",
        anti_goals=["generic dashboard cards", "text baked into imagery"],
    )
    return compile_godot_visual_prototype(topology, concept, trusted_png_asset(png()))


def test_registry_resolves_separate_visual_prototype_binding() -> None:
    binding = APPROVED_TOOLPACKS.binding_for("godot.visual-prototype")
    assert APPROVED_TOOLPACKS.resolve(binding) is GODOT_VISUAL_PROTOTYPE_TOOLPACK
    assert binding.version == "1.0.0"


def test_visual_compiler_is_deterministic_and_materializes_trusted_asset(tmp_path) -> None:
    first = artifact()
    second = artifact()
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.files == second.files
    destination = tmp_path / "product"
    GODOT_VISUAL_PROTOTYPE_TOOLPACK.execution_adapter.materialize(first, destination)
    image = destination / "assets" / "visual-foundation.png"
    assert hashlib.sha256(image.read_bytes()).hexdigest() == first.asset.sha256
    initial_scene = (destination / "scenes" / "entry.tscn").read_text(encoding="utf-8")
    assert 'path="res://assets/visual-foundation.png"' in initial_scene
    assert 'name="VisualFoundation" type="TextureRect"' in initial_scene


def test_visual_toolpack_rejects_asset_swap_and_bundle_tampering(tmp_path) -> None:
    approved = artifact()
    changed = dict(approved.files)
    changed["project.godot"] += "\n# unauthorized\n"
    tampered = CompiledGodotVisualPrototype(
        topology=approved.topology,
        concept=approved.concept,
        asset=approved.asset,
        plan_sha256=approved.plan_sha256,
        bundle_sha256=approved.bundle_sha256,
        files=changed,
    )
    with pytest.raises(PermissionError, match="bundle digest changed"):
        GODOT_VISUAL_PROTOTYPE_TOOLPACK.execution_adapter.materialize(tampered, tmp_path / "tampered")

    destination = tmp_path / "product"
    GODOT_VISUAL_PROTOTYPE_TOOLPACK.execution_adapter.materialize(approved, destination)
    (destination / approved.asset.path).write_bytes(png(257, 256))
    with pytest.raises(PermissionError, match="asset changed"):
        GODOT_VISUAL_PROTOTYPE_TOOLPACK.evidence_adapter.verify(
            approved, destination, tmp_path / "evidence", ["The rendered screen is visible."]
        )
