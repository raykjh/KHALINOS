"""Reusable least-authority Capability Packs for bounded Godot 2D profiles."""

from __future__ import annotations

import json
import re

from khalinos.toolpacks import CapabilityPackManifest, CapabilityPackStage
from khalinos.licensed_visual_assets import (
    ASSET_SELECTION_PATH,
    LICENSE_RECEIPT_PATH,
    LICENSED_ATLAS_MANIFEST_PATH,
    LICENSED_ATLAS_PATH,
    STYLE_COMPOSITION_PATH,
    LicensedArtBundle,
)
from khalinos.generated_vfx_assets import (
    EFFECT_ATLAS_MANIFEST_PATH,
    EFFECT_ATLAS_PATH,
    EFFECT_RECEIPT_PATH,
    EFFECT_SELECTION_PATH,
    EffectBundle,
)
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
GODOT_PRESENTATION_SKIN_PACK = CapabilityPackManifest(
    pack_id="godot.presentation-skin",
    version="1.0.0",
    provides=("presentation.skin",),
    requires=("godot.visual.foundation",),
    text_paths=("scripts/khalinos_presentation_skin.gd",),
)
GODOT_AUDIO_FEEDBACK_PACK = CapabilityPackManifest(
    pack_id="godot.audio-feedback",
    version="1.0.0",
    provides=("audio.feedback",),
    requires=("gameplay.combat-feedback",),
    text_paths=("scripts/khalinos_audio_feedback.gd",),
)
GODOT_ASSET_SELECTOR_PACK = CapabilityPackManifest(
    pack_id="godot.asset-selector",
    version="1.0.0",
    provides=("visual.asset.selection",),
    requires=("godot.visual.foundation",),
    text_paths=(ASSET_SELECTION_PATH,),
)
GODOT_STYLE_COMPOSER_PACK = CapabilityPackManifest(
    pack_id="godot.style-composer",
    version="1.0.0",
    provides=("visual.style.composition",),
    requires=("visual.asset.selection",),
    text_paths=(STYLE_COMPOSITION_PATH, "scripts/khalinos_licensed_art.gd"),
)
GODOT_LICENSED_ATLAS_PACK = CapabilityPackManifest(
    pack_id="godot.licensed-atlas",
    version="1.0.0",
    provides=("godot.visual.licensed-atlas",),
    requires=("visual.style.composition",),
    text_paths=(LICENSED_ATLAS_MANIFEST_PATH,),
    binary_paths=(LICENSED_ATLAS_PATH,),
)
GODOT_LICENSE_RECEIPT_PACK = CapabilityPackManifest(
    pack_id="godot.license-receipt",
    version="1.0.0",
    provides=("evidence.asset-license-receipt",),
    requires=("godot.visual.licensed-atlas",),
    text_paths=(LICENSE_RECEIPT_PATH,),
)
GODOT_EFFECT_SELECTOR_PACK = CapabilityPackManifest(
    pack_id="godot.effect-selector",
    version="1.0.0",
    provides=("visual.effect.selection",),
    requires=("gameplay.combat-feedback",),
    text_paths=(EFFECT_SELECTION_PATH,),
)
GODOT_EFFECT_ATLAS_PACK = CapabilityPackManifest(
    pack_id="godot.effect-atlas",
    version="1.0.0",
    provides=("godot.visual.effect-atlas",),
    requires=("visual.effect.selection",),
    text_paths=(EFFECT_ATLAS_MANIFEST_PATH,),
    binary_paths=(EFFECT_ATLAS_PATH,),
)
GODOT_VFX_PLAYER_PACK = CapabilityPackManifest(
    pack_id="godot.vfx-player",
    version="1.0.0",
    provides=("gameplay.vfx.playback",),
    requires=("godot.visual.effect-atlas",),
    text_paths=("scripts/khalinos_vfx_player.gd",),
)
GODOT_EFFECT_RECEIPT_PACK = CapabilityPackManifest(
    pack_id="godot.effect-receipt",
    version="1.0.0",
    provides=("evidence.effect-receipt",),
    requires=("gameplay.vfx.playback",),
    text_paths=(EFFECT_RECEIPT_PATH,),
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


PRESENTATION_SKIN_SCRIPT = r'''extends RefCounted

const PACK_ID := "godot.presentation-skin@1.0.0"

static func draw_parallax(canvas: CanvasItem, width: float, height: float, progress: float) -> void:
    var far_offset := fmod(progress * 0.08, 240.0)
    var near_offset := fmod(progress * 0.22, 180.0)
    for index in range(7):
        var x := float(index * 240) - far_offset - 120.0
        canvas.draw_colored_polygon(PackedVector2Array([
            Vector2(x - 150.0, height * 0.62),
            Vector2(x, height * 0.27),
            Vector2(x + 150.0, height * 0.62),
        ]), Color(0.18, 0.31, 0.28, 0.30))
    for index in range(8):
        var x := float(index * 180) - near_offset - 70.0
        canvas.draw_rect(Rect2(x - 9.0, height * 0.43, 18.0, height * 0.29), Color(0.18, 0.31, 0.20, 0.66), true)
        canvas.draw_circle(Vector2(x, height * 0.40), 56.0, Color(0.24, 0.46, 0.28, 0.62))
        canvas.draw_circle(Vector2(x - 31.0, height * 0.44), 37.0, Color(0.31, 0.56, 0.31, 0.48))
    canvas.draw_rect(Rect2(0.0, height * 0.72, width, height * 0.28), Color(0.21, 0.18, 0.12, 0.30), true)
    for index in range(12):
        var x := fmod(float(index * 104) - progress * 0.48, width + 104.0) - 52.0
        canvas.draw_line(Vector2(x, height * 0.80), Vector2(x + 32.0, height * 0.76), Color(0.95, 0.84, 0.48, 0.34), 3.0)

static func draw_side_scroll_party(canvas: CanvasItem, origin: Vector2, pulse: float) -> void:
    var warrior := origin + Vector2(-28.0, 2.0)
    canvas.draw_colored_polygon(PackedVector2Array([
        warrior + Vector2(-17.0, 25.0), warrior + Vector2(-13.0, -13.0),
        warrior + Vector2(13.0, -13.0), warrior + Vector2(19.0, 25.0),
    ]), Color("b86b35"))
    canvas.draw_circle(warrior + Vector2(0.0, -22.0), 12.0, Color("e8bd82"))
    canvas.draw_rect(Rect2(warrior + Vector2(-15.0, -12.0), Vector2(30.0, 20.0)), Color("c98b42"), true)
    canvas.draw_line(warrior + Vector2(13.0, -7.0), warrior + Vector2(28.0 + pulse, -27.0), Color("e9edf0"), 5.0)
    canvas.draw_line(warrior + Vector2(9.0, -3.0), warrior + Vector2(19.0, 7.0), Color("5f412b"), 4.0)

    var archer := origin + Vector2(8.0, 20.0)
    canvas.draw_colored_polygon(PackedVector2Array([
        archer + Vector2(-14.0, 22.0), archer + Vector2(-10.0, -12.0),
        archer + Vector2(11.0, -12.0), archer + Vector2(16.0, 22.0),
    ]), Color("456fa8"))
    canvas.draw_circle(archer + Vector2(0.0, -20.0), 11.0, Color("dfb77e"))
    canvas.draw_arc(archer + Vector2(17.0, -4.0), 17.0, -PI / 2.0, PI / 2.0, 12, Color("d9b66b"), 3.0)
    canvas.draw_line(archer + Vector2(17.0, -21.0), archer + Vector2(17.0, 13.0), Color("f3e3b0"), 2.0)

    var healer := origin + Vector2(30.0, -6.0)
    canvas.draw_colored_polygon(PackedVector2Array([
        healer + Vector2(-17.0, 25.0), healer + Vector2(-9.0, -12.0),
        healer + Vector2(10.0, -12.0), healer + Vector2(18.0, 25.0),
    ]), Color("e6d67f"))
    canvas.draw_circle(healer + Vector2(0.0, -21.0), 11.0, Color("f0ca92"))
    canvas.draw_line(healer + Vector2(14.0, -8.0), healer + Vector2(14.0, 24.0), Color("7a5233"), 4.0)
    canvas.draw_circle(healer + Vector2(14.0, -14.0), 7.0 + pulse * 0.15, Color(0.42, 1.0, 0.76, 0.88), false, 3.0)

static func draw_side_scroll_enemy(canvas: CanvasItem, position: Vector2, hp_ratio: float, pulse: float) -> void:
    canvas.draw_colored_polygon(PackedVector2Array([
        position + Vector2(-23.0, 25.0), position + Vector2(-18.0, -17.0),
        position + Vector2(-8.0, -28.0), position + Vector2(0.0, -20.0),
        position + Vector2(10.0, -30.0), position + Vector2(20.0, -15.0),
        position + Vector2(24.0, 25.0),
    ]), Color("2f7f48"))
    canvas.draw_circle(position + Vector2(0.0, -20.0), 16.0 + pulse * 0.08, Color("63b85b"))
    canvas.draw_colored_polygon(PackedVector2Array([
        position + Vector2(-12.0, -31.0), position + Vector2(-21.0, -42.0), position + Vector2(-5.0, -34.0),
    ]), Color("d8d0a6"))
    canvas.draw_colored_polygon(PackedVector2Array([
        position + Vector2(12.0, -31.0), position + Vector2(21.0, -42.0), position + Vector2(5.0, -34.0),
    ]), Color("d8d0a6"))
    canvas.draw_circle(position + Vector2(-6.0, -22.0), 2.5, Color("fff0a0"))
    canvas.draw_circle(position + Vector2(6.0, -22.0), 2.5, Color("fff0a0"))
    canvas.draw_rect(Rect2(position.x - 24.0, position.y - 52.0, 48.0, 6.0), Color("2a2430"), true)
    canvas.draw_rect(Rect2(position.x - 22.0, position.y - 50.0, 44.0 * clampf(hp_ratio, 0.0, 1.0), 3.0), Color("ff6558"), true)

static func draw_destination(canvas: CanvasItem, position: Vector2, reached: bool) -> void:
    var glow := Color(1.0, 0.83, 0.30, 0.38 if not reached else 0.72)
    canvas.draw_circle(position + Vector2(0.0, 17.0), 48.0, glow, false, 5.0, true)
    canvas.draw_line(position + Vector2(0.0, -50.0), position + Vector2(0.0, 45.0), Color("fff7dc"), 7.0)
    canvas.draw_colored_polygon(PackedVector2Array([
        position + Vector2(4.0, -48.0), position + Vector2(62.0, -28.0), position + Vector2(4.0, -8.0),
    ]), Color("df4d43" if not reached else "f4c84d"))
    canvas.draw_circle(position + Vector2(0.0, -54.0), 7.0, Color("fff1b8"))
    canvas.draw_string(ThemeDB.fallback_font, position + Vector2(-62.0, 68.0), "DESTINATION", HORIZONTAL_ALIGNMENT_CENTER, 124.0, 15, Color("fff1b8"))

static func draw_hud_panel(canvas: CanvasItem, rect: Rect2, accent: Color) -> void:
    canvas.draw_rect(rect, Color(0.025, 0.055, 0.075, 0.86), true)
    canvas.draw_rect(rect, Color(accent, 0.88), false, 2.0)
    canvas.draw_line(rect.position + Vector2(10.0, 7.0), Vector2(rect.end.x - 10.0, rect.position.y + 7.0), Color(accent, 0.52), 2.0)

static func draw_top_down_arena(canvas: CanvasItem, center: Vector2, width: float, height: float) -> void:
    canvas.draw_circle(center, minf(width, height) * 0.36, Color(0.58, 0.83, 0.50, 0.10), false, 3.0, true)
    canvas.draw_circle(center, minf(width, height) * 0.22, Color(0.95, 0.78, 0.34, 0.10), false, 2.0, true)
    for angle_index in range(8):
        var angle := TAU * float(angle_index) / 8.0
        var inner := center + Vector2.from_angle(angle) * minf(width, height) * 0.28
        var outer := center + Vector2.from_angle(angle) * minf(width, height) * 0.34
        canvas.draw_line(inner, outer, Color(0.78, 0.92, 0.62, 0.25), 3.0)
'''


AUDIO_FEEDBACK_SCRIPT = r'''extends RefCounted

const PACK_ID := "godot.audio-feedback@1.0.0"
const MIX_RATE := 22050

static func _cue_spec(cue: String) -> Dictionary:
    match cue:
        "attack":
            return {"frequencies": [520.0, 780.0], "duration": 0.10, "volume": 0.24}
        "hit":
            return {"frequencies": [150.0, 210.0], "duration": 0.13, "volume": 0.30}
        "heal":
            return {"frequencies": [660.0, 880.0], "duration": 0.24, "volume": 0.22}
        "victory":
            return {"frequencies": [523.25, 659.25, 783.99], "duration": 0.52, "volume": 0.20}
        _:
            return {"frequencies": [330.0], "duration": 0.08, "volume": 0.18}

static func build_cue(cue: String) -> AudioStreamWAV:
    var spec := _cue_spec(cue)
    var frame_count := int(float(spec.duration) * MIX_RATE)
    var bytes := PackedByteArray()
    bytes.resize(frame_count * 2)
    for frame in range(frame_count):
        var time := float(frame) / float(MIX_RATE)
        var envelope := minf(1.0, time * 45.0) * maxf(0.0, 1.0 - time / float(spec.duration))
        var sample := 0.0
        for frequency in spec.frequencies:
            sample += sin(TAU * float(frequency) * time)
        sample /= maxf(1.0, float(spec.frequencies.size()))
        var value := int(clampf(sample * envelope * float(spec.volume), -1.0, 1.0) * 32767.0)
        bytes.encode_s16(frame * 2, value)
    var stream := AudioStreamWAV.new()
    stream.format = AudioStreamWAV.FORMAT_16_BITS
    stream.mix_rate = MIX_RATE
    stream.stereo = false
    stream.data = bytes
    return stream

static func play_cue(host: Node, cue: String) -> bool:
    if host == null or not host.is_inside_tree():
        return false
    var player := AudioStreamPlayer.new()
    player.name = "KHALINOS_%s_SFX" % cue.to_upper()
    player.stream = build_cue(cue)
    player.volume_db = -8.0
    host.add_child(player)
    player.finished.connect(player.queue_free)
    player.play()
    return true
'''


LICENSED_ART_SCRIPT = r'''extends RefCounted

const PACK_ID := "godot.style-composer@1.0.0"

static func region_for(manifest: Dictionary, role: String) -> Rect2:
    for slot in manifest.get("slots", []):
        if String(slot.get("role", "")) == role:
            var region: Array = slot.get("atlas_region", [])
            if region.size() == 4:
                return Rect2(float(region[0]), float(region[1]), float(region[2]), float(region[3]))
    return Rect2()

static func draw_role(
    canvas: CanvasItem,
    texture: Texture2D,
    manifest: Dictionary,
    role: String,
    destination: Rect2,
    modulate := Color.WHITE,
) -> bool:
    if texture == null:
        return false
    var region := region_for(manifest, role)
    if region.size == Vector2.ZERO:
        return false
    canvas.draw_texture_rect_region(texture, destination, region, modulate)
    return true
'''


VFX_PLAYER_SCRIPT = r'''extends RefCounted

const PACK_ID := "godot.vfx-player@1.0.0"

static func slot_for(manifest: Dictionary, role: String) -> Dictionary:
    for slot in manifest.get("slots", []):
        if String(slot.get("role", "")) == role:
            return slot
    return {}

static func frame_region(
    manifest: Dictionary,
    role: String,
    life: float,
    max_life: float,
) -> Rect2:
    var slot := slot_for(manifest, role)
    if slot.is_empty():
        return Rect2()
    var frames := int(slot.get("frames", 0))
    var size := int(slot.get("frame_size", 0))
    if frames <= 0 or size <= 0:
        return Rect2()
    var progress := clampf(1.0 - life / maxf(0.001, max_life), 0.0, 0.9999)
    var frame := mini(frames - 1, int(floor(progress * float(frames))))
    return Rect2(frame * size, int(slot.get("row", 0)) * size, size, size)

static func draw_effect(
    canvas: CanvasItem,
    texture: Texture2D,
    manifest: Dictionary,
    role: String,
    destination: Rect2,
    life: float,
    max_life: float,
    modulate := Color.WHITE,
) -> bool:
    if texture == null:
        return false
    var region := frame_region(manifest, role, life, max_life)
    if region.size == Vector2.ZERO:
        return false
    canvas.draw_texture_rect_region(texture, destination, region, modulate)
    return true
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


def godot_presentation_skin_stage() -> CapabilityPackStage:
    """Provide shared presentation primitives without owning gameplay rules."""

    return CapabilityPackStage(
        manifest=GODOT_PRESENTATION_SKIN_PACK,
        text_files={"scripts/khalinos_presentation_skin.gd": PRESENTATION_SKIN_SCRIPT},
    )


def godot_audio_feedback_stage() -> CapabilityPackStage:
    """Provide deterministic, copyright-safe synthesized gameplay cues."""

    return CapabilityPackStage(
        manifest=GODOT_AUDIO_FEEDBACK_PACK,
        text_files={"scripts/khalinos_audio_feedback.gd": AUDIO_FEEDBACK_SCRIPT},
    )


def godot_licensed_art_stages(bundle: LicensedArtBundle) -> tuple[CapabilityPackStage, ...]:
    """Bind a pre-graded licensed asset selection without redistributing its source library."""

    text = bundle.text_files()
    return (
        CapabilityPackStage(
            manifest=GODOT_ASSET_SELECTOR_PACK,
            text_files={ASSET_SELECTION_PATH: text[ASSET_SELECTION_PATH]},
        ),
        CapabilityPackStage(
            manifest=GODOT_STYLE_COMPOSER_PACK,
            text_files={
                STYLE_COMPOSITION_PATH: text[STYLE_COMPOSITION_PATH],
                "scripts/khalinos_licensed_art.gd": LICENSED_ART_SCRIPT,
            },
        ),
        CapabilityPackStage(
            manifest=GODOT_LICENSED_ATLAS_PACK,
            text_files={LICENSED_ATLAS_MANIFEST_PATH: text[LICENSED_ATLAS_MANIFEST_PATH]},
            binary_paths=(LICENSED_ATLAS_PATH,),
        ),
        CapabilityPackStage(
            manifest=GODOT_LICENSE_RECEIPT_PACK,
            text_files={LICENSE_RECEIPT_PATH: text[LICENSE_RECEIPT_PATH]},
        ),
    )


def godot_effect_stages(bundle: EffectBundle) -> tuple[CapabilityPackStage, ...]:
    """Bind generated combat VFX through selection, atlas, playback, and receipt stages."""

    text = bundle.text_files()
    return (
        CapabilityPackStage(
            manifest=GODOT_EFFECT_SELECTOR_PACK,
            text_files={EFFECT_SELECTION_PATH: text[EFFECT_SELECTION_PATH]},
        ),
        CapabilityPackStage(
            manifest=GODOT_EFFECT_ATLAS_PACK,
            text_files={EFFECT_ATLAS_MANIFEST_PATH: text[EFFECT_ATLAS_MANIFEST_PATH]},
            binary_paths=(EFFECT_ATLAS_PATH,),
        ),
        CapabilityPackStage(
            manifest=GODOT_VFX_PLAYER_PACK,
            text_files={"scripts/khalinos_vfx_player.gd": VFX_PLAYER_SCRIPT},
        ),
        CapabilityPackStage(
            manifest=GODOT_EFFECT_RECEIPT_PACK,
            text_files={EFFECT_RECEIPT_PATH: text[EFFECT_RECEIPT_PATH]},
        ),
    )
