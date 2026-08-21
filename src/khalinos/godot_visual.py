"""Trusted compiler for an asset-assisted, bounded Godot visual prototype."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from khalinos.godot_topology import GodotTopologyPlan, compile_godot_topology
from khalinos.models import ArtifactAsset, VisualConcept
from khalinos.visual_assets import ASSET_PATH


def _sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CompiledGodotVisualPrototype(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-compiled-godot-visual-prototype-v1"] = (
        "khalinos-compiled-godot-visual-prototype-v1"
    )
    topology: GodotTopologyPlan
    concept: VisualConcept
    asset: ArtifactAsset
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: dict[str, str] = Field(min_length=8, max_length=24)


VISUAL_PROBE_SCRIPT = '''extends SceneTree

func _initialize() -> void:
    call_deferred("_probe")

func _probe() -> void:
    var output := ""
    for argument in OS.get_cmdline_user_args():
        if argument.begins_with("--output="):
            output = argument.trim_prefix("--output=")
    if output.is_empty():
        quit(2)
        return
    var source := FileAccess.open("res://KHALINOS_TOPOLOGY.json", FileAccess.READ)
    var manifest = JSON.parse_string(source.get_as_text())
    var initial_path := ""
    for region in manifest.regions:
        if region.region_id == manifest.initial_region:
            initial_path = region.scene_path
    var packed = load(initial_path)
    var instance = packed.instantiate() if packed != null else null
    var visual = instance.get_node_or_null("VisualFoundation") if instance != null else null
    var scrim = instance.get_node_or_null("Background") if instance != null else null
    var receipt := {
        "schema_version": "khalinos-godot-visual-probe-v1",
        "initial_scene_loaded": instance != null,
        "texture_ready": visual != null and visual.texture != null,
        "scrim_translucent": scrim != null and scrim.color.a > 0.0 and scrim.color.a < 0.8,
    }
    receipt.passed = receipt.initial_scene_loaded and receipt.texture_ready and receipt.scrim_translucent
    var target := FileAccess.open(output, FileAccess.WRITE)
    target.store_string(JSON.stringify(receipt))
    target.close()
    if instance != null:
        instance.free()
    quit(0 if receipt.passed else 1)
'''


def _visual_scene(source: str) -> str:
    source = source.replace("[gd_scene load_steps=2 format=3]", "[gd_scene load_steps=3 format=3]")
    source = source.replace(
        '[ext_resource type="Script" path="res://scripts/khalinos_topology_region.gd" id="1"]',
        '[ext_resource type="Script" path="res://scripts/khalinos_topology_region.gd" id="1"]\n'
        '[ext_resource type="Texture2D" path="res://assets/visual-foundation.png" id="2_visual"]',
    )
    background = '''[node name="VisualFoundation" type="TextureRect" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
texture = ExtResource("2_visual")
expand_mode = 1
stretch_mode = 6
mouse_filter = 2

'''
    source = source.replace('[node name="Background" type="ColorRect" parent="."]', background + '[node name="Background" type="ColorRect" parent="."]')
    source = source.replace(", 1)\n\n[node name=\"Margin\"", ", 0.58)\n\n[node name=\"Margin\"")
    return source


def compile_godot_visual_prototype(
    topology: GodotTopologyPlan,
    concept: VisualConcept,
    asset: ArtifactAsset,
) -> CompiledGodotVisualPrototype:
    if asset.path != ASSET_PATH or asset.media_type != "image/png":
        raise ValueError("Godot visual prototype requires the trusted visual foundation PNG")
    base = compile_godot_topology(topology)
    plan_sha = _sha256({
        "topology": topology.model_dump(mode="json"),
        "concept": concept.model_dump(mode="json"),
        "asset_sha256": asset.sha256,
    })
    files = dict(base.files)
    files["scripts/khalinos_topology_region.gd"] = files[
        "scripts/khalinos_topology_region.gd"
    ].replace(
        '    $Margin/VBox/Region.text = region_id.to_upper().replace("_", " ")\n'
        '    $Margin/VBox/Kind.text = region_kind.to_upper()\n',
        "",
    )
    files["scripts/khalinos_visual_probe.gd"] = VISUAL_PROBE_SCRIPT
    for path in tuple(files):
        if path.startswith("scenes/") and path.endswith(".tscn"):
            files[path] = _visual_scene(files[path])
    manifest = {
        "schema_version": "khalinos-godot-visual-prototype-v1",
        "candidate_id": concept.candidate_id,
        "concept_name": concept.name,
        "topology_sha256": base.plan_sha256,
        "asset_path": asset.path,
        "asset_sha256": asset.sha256,
        "plan_sha256": plan_sha,
    }
    files["KHALINOS_VISUAL_PROTOTYPE.json"] = json.dumps(
        manifest, ensure_ascii=False, indent=2
    ) + "\n"
    files = {path: content.replace("\r\n", "\n").replace("\r", "\n") for path, content in files.items()}
    return CompiledGodotVisualPrototype(
        topology=topology,
        concept=concept,
        asset=asset,
        plan_sha256=plan_sha,
        bundle_sha256=_sha256({
            "plan_sha256": plan_sha,
            "files": files,
            "asset_sha256": asset.sha256,
        }),
        files=files,
    )
