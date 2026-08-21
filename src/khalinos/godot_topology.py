"""Trusted compiler for a bounded Godot screen-topology plan."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from khalinos.models import QuestPlan


def _sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GodotRegionKind(StrEnum):
    SCREEN = "screen"
    OVERLAY = "overlay"


class GodotRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,47}$")
    label: str = Field(min_length=1, max_length=80)
    kind: GodotRegionKind = GodotRegionKind.SCREEN
    transitions: tuple[str, ...] = Field(default=(), max_length=8)
    background_hex: str = Field(default="172033", pattern=r"^[A-Fa-f0-9]{6}$")


class GodotTopologyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-godot-topology-plan-v1"] = "khalinos-godot-topology-plan-v1"
    project_name: str = Field(min_length=2, max_length=80)
    initial_region: str = Field(pattern=r"^[a-z][a-z0-9_]{1,47}$")
    regions: tuple[GodotRegion, ...] = Field(min_length=2, max_length=16)
    viewport_width: int = Field(default=1280, ge=640, le=3840)
    viewport_height: int = Field(default=720, ge=360, le=2160)

    @model_validator(mode="after")
    def connected(self) -> "GodotTopologyPlan":
        identifiers = tuple(item.region_id for item in self.regions)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Godot topology region IDs must be unique")
        known = set(identifiers)
        if self.initial_region not in known:
            raise ValueError("Godot topology initial region is not declared")
        by_id = {item.region_id: item for item in self.regions}
        for item in self.regions:
            unknown = set(item.transitions) - known
            if unknown:
                raise ValueError(f"Godot topology references unknown regions: {sorted(unknown)}")
            if item.region_id in item.transitions:
                raise ValueError("Godot topology region cannot transition to itself")
        reached: set[str] = set()
        pending = [self.initial_region]
        while pending:
            current = pending.pop()
            if current in reached:
                continue
            reached.add(current)
            pending.extend(by_id[current].transitions)
        if known - reached:
            raise ValueError(f"Godot topology contains unreachable regions: {sorted(known - reached)}")
        return self


class CompiledGodotTopology(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-compiled-godot-topology-v1"] = "khalinos-compiled-godot-topology-v1"
    plan: GodotTopologyPlan
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: dict[str, str] = Field(min_length=6, max_length=20)


class GodotProjectPlan(BaseModel):
    """The only model-authored contract accepted by the Godot workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-godot-project-plan-v1"] = "khalinos-godot-project-plan-v1"
    quest_plan: QuestPlan
    topology: GodotTopologyPlan


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _color(value: str) -> tuple[float, float, float]:
    return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))


def _region_script() -> str:
    return '''extends Control

@export var region_id: String = ""
@export var region_kind: String = "screen"
@export var transitions: PackedStringArray = []

func _ready() -> void:
    $Margin/VBox/Region.text = region_id.to_upper().replace("_", " ")
    $Margin/VBox/Kind.text = region_kind.to_upper()
    for target in transitions:
        var button := Button.new()
        button.text = "Open " + target.replace("_", " ").capitalize()
        button.custom_minimum_size = Vector2(0, 56)
        button.pressed.connect(_open.bind(target))
        $Margin/VBox/Actions.add_child(button)

func _open(target: String) -> void:
    get_tree().change_scene_to_file("res://scenes/" + target + ".tscn")
'''


def _probe_script() -> str:
    return '''extends SceneTree

func _initialize() -> void:
    call_deferred("_probe")

func _argument(prefix: String) -> String:
    for argument in OS.get_cmdline_user_args():
        if argument.begins_with(prefix):
            return argument.trim_prefix(prefix)
    return ""

func _probe() -> void:
    var output := _argument("--output=")
    if output.is_empty():
        quit(2)
        return
    var source := FileAccess.open("res://KHALINOS_TOPOLOGY.json", FileAccess.READ)
    if source == null:
        quit(3)
        return
    var manifest = JSON.parse_string(source.get_as_text())
    var visited: Array[String] = []
    var errors: Array[String] = []
    for region in manifest.regions:
        var packed = load(region.scene_path)
        if packed == null:
            errors.append("unloadable:" + region.region_id)
            continue
        var instance = packed.instantiate()
        if instance == null or instance.get("region_id") != region.region_id:
            errors.append("identity_mismatch:" + region.region_id)
        else:
            visited.append(region.region_id)
        if instance != null:
            instance.free()
    var receipt := {"schema_version": "khalinos-godot-topology-probe-v1", "visited": visited, "errors": errors, "passed": errors.is_empty() and visited.size() == manifest.regions.size()}
    var target := FileAccess.open(output, FileAccess.WRITE)
    target.store_string(JSON.stringify(receipt))
    target.close()
    quit(0 if receipt.passed else 1)
'''


def _scene(region: GodotRegion) -> str:
    red, green, blue = _color(region.background_hex)
    transitions = "PackedStringArray(" + ", ".join(_quoted(item) for item in region.transitions) + ")"
    return f'''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/khalinos_topology_region.gd" id="1"]

[node name="Region" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
script = ExtResource("1")
region_id = {_quoted(region.region_id)}
region_kind = {_quoted(region.kind.value)}
transitions = {transitions}

[node name="Background" type="ColorRect" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
color = Color({red:.6f}, {green:.6f}, {blue:.6f}, 1)

[node name="Margin" type="MarginContainer" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
offset_left = 80.0
offset_top = 70.0
offset_right = -80.0
offset_bottom = -70.0
grow_horizontal = 2
grow_vertical = 2

[node name="VBox" type="VBoxContainer" parent="Margin"]
layout_mode = 2
theme_override_constants/separation = 18
alignment = 1

[node name="Kind" type="Label" parent="Margin/VBox"]
layout_mode = 2
theme_override_font_sizes/font_size = 16
text = {_quoted(region.kind.value.upper())}
horizontal_alignment = 1

[node name="Region" type="Label" parent="Margin/VBox"]
layout_mode = 2
theme_override_font_sizes/font_size = 46
text = {_quoted(region.label)}
horizontal_alignment = 1

[node name="Actions" type="VBoxContainer" parent="Margin/VBox"]
layout_mode = 2
theme_override_constants/separation = 10
'''


def compile_godot_topology(plan: GodotTopologyPlan) -> CompiledGodotTopology:
    scene_paths = {item.region_id: f"scenes/{item.region_id}.tscn" for item in plan.regions}
    manifest = {
        "schema_version": "khalinos-godot-runtime-topology-v1",
        "initial_region": plan.initial_region,
        "regions": [
            {
                "region_id": item.region_id,
                "kind": item.kind.value,
                "scene_path": "res://" + scene_paths[item.region_id],
                "transitions": list(item.transitions),
            }
            for item in plan.regions
        ],
    }
    safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "", plan.project_name).strip() or "KHALINOS Project"
    files = {
        "project.godot": f'''[application]
config/name={_quoted(safe_name)}
run/main_scene={_quoted("res://" + scene_paths[plan.initial_region])}

[display]
window/size/viewport_width={plan.viewport_width}
window/size/viewport_height={plan.viewport_height}

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
''',
        "scripts/khalinos_topology_region.gd": _region_script(),
        "scripts/khalinos_topology_probe.gd": _probe_script(),
        "KHALINOS_TOPOLOGY.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        **{scene_paths[item.region_id]: _scene(item) for item in plan.regions},
    }
    files = {path: content.replace("\r\n", "\n").replace("\r", "\n") for path, content in files.items()}
    plan_sha = _sha256(plan)
    return CompiledGodotTopology(
        plan=plan,
        plan_sha256=plan_sha,
        bundle_sha256=_sha256({"plan_sha256": plan_sha, "files": files}),
        files=files,
    )
