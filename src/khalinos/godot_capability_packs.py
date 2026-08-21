"""Reusable least-authority Capability Packs for bounded Godot 2D profiles."""

from __future__ import annotations

import json
import re

from khalinos.toolpacks import CapabilityPackManifest, CapabilityPackStage
from khalinos.visual_assets import ASSET_PATH


GODOT_PROJECT_CORE_PACK = CapabilityPackManifest(
    pack_id="godot.project-core",
    version="1.0.0",
    provides=("godot.project",),
    text_paths=("README.md", "project.godot"),
)
GODOT_VISUAL_FOUNDATION_PACK = CapabilityPackManifest(
    pack_id="godot.visual-foundation",
    version="1.0.0",
    provides=("godot.visual.foundation",),
    requires=("godot.project",),
    text_paths=("scenes/gameplay.tscn",),
    binary_paths=(ASSET_PATH,),
)
GODOT_COMBAT_FEEDBACK_PACK = CapabilityPackManifest(
    pack_id="godot.combat-feedback",
    version="1.0.0",
    provides=("gameplay.combat-feedback",),
    requires=("gameplay.auto-attack",),
    text_paths=("scripts/khalinos_combat_feedback.gd",),
)


COMBAT_FEEDBACK_SCRIPT = r'''extends RefCounted

const PACK_ID := "godot.combat-feedback@1.0.0"

static func draw_attack_range(
    canvas: CanvasItem,
    origin: Vector2,
    radius: float,
    color: Color,
    filled: bool = false,
    width: float = 1.5,
    antialiased: bool = true,
) -> void:
    canvas.draw_circle(origin, radius, color, filled, width, antialiased)

static func draw_attack_line(
    canvas: CanvasItem,
    origin: Vector2,
    target: Vector2,
    color: Color,
    width: float,
    antialiased: bool = true,
) -> void:
    canvas.draw_line(origin, target, color, width, antialiased)

static func draw_basic_attack(canvas: CanvasItem, effect: Dictionary) -> void:
    var progress: float = 1.0 - float(effect.life) / max(0.01, float(effect.max_life))
    var attack_color := Color(1.0, 0.68, 0.22, 0.94 * (1.0 - progress))
    var width := 7.0
    if String(effect.role) == "damage":
        attack_color = Color(1.0, 0.94, 0.30, 0.96 * (1.0 - progress))
        width = 4.0
    elif String(effect.role) == "support":
        attack_color = Color(0.35, 0.92, 1.0, 0.94 * (1.0 - progress))
        width = 5.0
    draw_attack_line(canvas, effect.origin, effect.target, attack_color, width)
    canvas.draw_circle(effect.target, 8.0 + progress * 12.0, attack_color, false, 3.0, true)
    draw_attack_range(
        canvas,
        effect.origin,
        float(effect.range),
        Color(attack_color, 0.10 * (1.0 - progress)),
    )

static func draw_skill(canvas: CanvasItem, effect: Dictionary, center: Vector2) -> void:
    var progress: float = 1.0 - float(effect.life) / max(0.01, float(effect.max_life))
    var alpha: float = 0.78 * (1.0 - progress)
    var kind := String(effect.kind)
    var effect_color := Color(1.0, 0.68, 0.18, alpha)
    if kind == "heal":
        effect_color = Color(0.25, 1.0, 0.62, alpha)
        canvas.draw_circle(
            center,
            float(effect.radius) * (0.30 + progress * 0.25),
            Color(0.20, 0.92, 0.55, alpha * 0.18),
        )
    elif kind == "shield":
        effect_color = Color(0.35, 0.72, 1.0, alpha)
    elif kind == "resurrection":
        effect_color = Color(0.88, 0.72, 1.0, alpha)
    canvas.draw_circle(
        center,
        float(effect.radius) * (0.72 + progress * 0.28),
        effect_color,
        false,
        5.0,
        true,
    )

static func draw_enemy_attack(canvas: CanvasItem, effect: Dictionary) -> void:
    var progress: float = 1.0 - float(effect.life) / max(0.01, float(effect.max_life))
    var color := Color(1.0, 0.18, 0.12, 0.95 * (1.0 - progress))
    draw_attack_line(canvas, effect.position, effect.target, color, 8.0)
    canvas.draw_circle(effect.target, 12.0 + progress * 14.0, color, false, 4.0, true)
'''


def godot_project_core_stage(
    *,
    project_name: str,
    viewport_width: int,
    viewport_height: int,
    readme_body: str,
) -> CapabilityPackStage:
    """Produce the common project shell without selecting a gameplay genre."""

    safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "", project_name).strip() or "KHALINOS Game"
    return CapabilityPackStage(
        manifest=GODOT_PROJECT_CORE_PACK,
        text_files={
            "project.godot": f'''[application]\nconfig/name={json.dumps(safe_name)}\nrun/main_scene="res://scenes/gameplay.tscn"\n\n[display]\nwindow/size/viewport_width={viewport_width}\nwindow/size/viewport_height={viewport_height}\nwindow/size/window_width_override={viewport_width}\nwindow/size/window_height_override={viewport_height}\n\n[input]\nmove_left={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":65), Object(InputEventKey,"physical_keycode":4194311)]}}\nmove_right={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":68), Object(InputEventKey,"physical_keycode":4194313)]}}\nmove_up={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":87), Object(InputEventKey,"physical_keycode":4194320)]}}\nmove_down={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":83), Object(InputEventKey,"physical_keycode":4194322)]}}\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\nrenderer/rendering_method.mobile="gl_compatibility"\n''',
            "README.md": f"# {safe_name}\n\n{readme_body}\n",
        },
    )


def godot_visual_foundation_stage(
    *,
    viewport_width: int,
    viewport_height: int,
    script_path: str,
    node_name: str,
) -> CapabilityPackStage:
    """Bind one trusted visual foundation to a profile-owned gameplay script."""

    scene = f'''[gd_scene load_steps=3 format=3]\n\n[ext_resource type="Script" path="res://{script_path}" id="1"]\n[ext_resource type="Texture2D" path="res://assets/visual-foundation.png" id="2"]\n\n[node name="{node_name}" type="Node2D"]\nscript = ExtResource("1")\n\n[node name="VisualFoundation" type="TextureRect" parent="."]\noffset_right = {float(viewport_width):.1f}\noffset_bottom = {float(viewport_height):.1f}\ntexture = ExtResource("2")\nexpand_mode = 1\nstretch_mode = 6\nmouse_filter = 2\nmodulate = Color(1, 1, 1, 0.60)\nz_index = -2\n'''
    return CapabilityPackStage(
        manifest=GODOT_VISUAL_FOUNDATION_PACK,
        text_files={"scenes/gameplay.tscn": scene},
        binary_paths=(ASSET_PATH,),
    )


def godot_combat_feedback_stage() -> CapabilityPackStage:
    """Materialize shared combat-feedback drawing primitives after combat authority exists."""

    return CapabilityPackStage(
        manifest=GODOT_COMBAT_FEEDBACK_PACK,
        text_files={"scripts/khalinos_combat_feedback.gd": COMBAT_FEEDBACK_SCRIPT},
    )
