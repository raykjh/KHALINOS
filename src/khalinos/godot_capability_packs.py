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
