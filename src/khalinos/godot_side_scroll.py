"""Bounded side-scrolling auto-combat profile composed from Godot Capability Packs."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from khalinos.godot_capability_packs import (
    GODOT_ASSET_SELECTOR_PACK,
    GODOT_AUDIO_FEEDBACK_PACK,
    GODOT_COMBAT_FEEDBACK_PACK,
    GODOT_LICENSED_ATLAS_PACK,
    GODOT_LICENSE_RECEIPT_PACK,
    GODOT_PRESENTATION_SKIN_PACK,
    GODOT_PROJECT_CORE_PACK,
    GODOT_STYLE_COMPOSER_PACK,
    GODOT_VISUAL_FOUNDATION_PACK,
    GODOT_EFFECT_ATLAS_PACK,
    GODOT_EFFECT_RECEIPT_PACK,
    GODOT_EFFECT_SELECTOR_PACK,
    GODOT_VFX_PLAYER_PACK,
    godot_audio_feedback_stage,
    godot_combat_feedback_stage,
    godot_effect_stages,
    godot_licensed_art_stages,
    godot_presentation_skin_stage,
    godot_project_core_stage,
    godot_visual_foundation_stage,
)
from khalinos.generated_vfx_assets import EFFECT_ATLAS_PATH, EffectBundle
from khalinos.licensed_visual_assets import LICENSED_ATLAS_PATH, LicensedArtBundle
from khalinos.models import ArtifactAsset, QuestPlan, VisualConcept
from khalinos.toolpacks import (
    CapabilityComposition,
    CapabilityPackManifest,
    CapabilityPackStage,
    compose_capability_stages,
)
from khalinos.visual_assets import ASSET_PATH


SIDE_SCROLL_SCRIPT = r'''extends Node2D

const CombatFeedback = preload("res://scripts/khalinos_combat_feedback.gd")
const PresentationSkin = preload("res://scripts/khalinos_presentation_skin.gd")
const AudioFeedback = preload("res://scripts/khalinos_audio_feedback.gd")
const COMBAT_FEEDBACK_PACK_ID := CombatFeedback.PACK_ID
const PRESENTATION_SKIN_PACK_ID := PresentationSkin.PACK_ID
const AUDIO_FEEDBACK_PACK_ID := AudioFeedback.PACK_ID

var combat: Dictionary = {}
var destination: Dictionary = {}
var started := false
var won := false
var progress_distance := 0.0
var elapsed := 0.0
var spawn_clock := 0.0
var attack_clock := 0.0
var total_spawned := 0
var total_attacks := 0
var total_kills := 0
var enemies: Array[Dictionary] = []
var shot_effects: Array[Dictionary] = []
var audio_events := {"attack": 0, "hit": 0, "heal": 0, "victory": 0}
var licensed_art_manifest: Dictionary = {}
var licensed_art_texture: Texture2D
var licensed_art_helper
var effect_manifest: Dictionary = {}
var effect_texture: Texture2D
var effect_player

func _ready() -> void:
    combat = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_SIDE_SCROLL.json"))
    destination = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_DESTINATION.json"))
    if FileAccess.file_exists("res://KHALINOS_LICENSED_ATLAS.json"):
        licensed_art_manifest = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_LICENSED_ATLAS.json"))
        licensed_art_texture = load("res://assets/licensed-art-atlas.png")
        licensed_art_helper = load("res://scripts/khalinos_licensed_art.gd")
    if FileAccess.file_exists("res://KHALINOS_EFFECT_ATLAS.json"):
        effect_manifest = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_EFFECT_ATLAS.json"))
        effect_texture = load("res://assets/combat-vfx-atlas.png")
        effect_player = load("res://scripts/khalinos_vfx_player.gd")
    get_window().content_scale_size = Vector2i(int(combat.viewport_width), int(combat.viewport_height))
    get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
    queue_redraw()

func start_run() -> void:
    started = true

func _play_audio(cue: String) -> void:
    audio_events[cue] = int(audio_events.get(cue, 0)) + 1
    AudioFeedback.play_cue(self, cue)

func _process(delta: float) -> void:
    elapsed += delta
    if not started and elapsed >= 0.20:
        start_run()
    if started and not won:
        simulate_step(delta)
    queue_redraw()

func simulate_step(delta: float) -> void:
    if not started or won:
        return
    progress_distance = minf(
        float(destination["destination_distance"]),
        progress_distance + float(destination["party_speed"]) * delta
    )
    spawn_clock += delta
    if enemies.is_empty() or spawn_clock >= float(combat["enemy_spawn_interval"]):
        spawn_clock = 0.0
        enemies.append({
            "x": float(combat["viewport_width"]) - 90.0,
            "hp": float(combat["enemy_health"]),
        })
        total_spawned += 1
    for enemy in enemies:
        enemy["x"] = maxf(205.0, float(enemy["x"]) - float(combat["enemy_speed"]) * delta)
    attack_clock += delta
    var target = _nearest_enemy()
    if target != null and float(target["x"]) - 170.0 <= float(combat["attack_range"]):
        if attack_clock >= float(combat["attack_interval"]):
            attack_clock = 0.0
            target["hp"] = float(target["hp"]) - float(combat["attack_damage"])
            total_attacks += 1
            var vfx_role := "warrior_slash" if total_attacks % 2 == 1 else "archer_impact"
            shot_effects.append({"from": Vector2(190, 360), "to": Vector2(float(target["x"]), 360), "ttl": 0.45, "max_ttl": 0.45, "vfx_role": vfx_role})
            _play_audio("attack")
            _play_audio("hit")
            if float(target["hp"]) <= 0.0:
                enemies.erase(target)
                total_kills += 1
    for effect in shot_effects.duplicate():
        effect["ttl"] = float(effect["ttl"]) - delta
        if float(effect["ttl"]) <= 0.0:
            shot_effects.erase(effect)
    if progress_distance >= float(destination["destination_distance"]):
        won = true
        _play_audio("victory")

func _nearest_enemy():
    if enemies.is_empty():
        return null
    var nearest: Dictionary = enemies[0]
    for enemy in enemies:
        if float(enemy["x"]) < float(nearest["x"]):
            nearest = enemy
    return nearest

func _draw() -> void:
    var width := float(combat.get("viewport_width", 960))
    var height := float(combat.get("viewport_height", 540))
    # Preserve lane readability without hiding the selected visual-foundation
    # texture behind an opaque procedural backdrop.
    draw_rect(Rect2(0, 0, width, height), Color(0.74, 0.90, 0.94, 0.38), true)
    draw_rect(Rect2(0, height * 0.58, width, height * 0.42), Color(0.84, 0.77, 0.55, 0.58), true)
    draw_rect(Rect2(0, height * 0.72, width, height * 0.12), Color(0.56, 0.49, 0.34, 0.72), true)
    PresentationSkin.draw_parallax(self, width, height, progress_distance)
    if licensed_art_helper != null and licensed_art_texture != null:
        for prop_index in range(6):
            var prop_x := fposmod(float(prop_index * 211) - progress_distance * 0.22, width + 150.0) - 70.0
            var prop_role := "tree" if prop_index % 2 == 0 else "rock"
            var prop_size := Vector2(92, 92) if prop_role == "tree" else Vector2(64, 64)
            licensed_art_helper.draw_role(
                self,
                licensed_art_texture,
                licensed_art_manifest,
                prop_role,
                Rect2(Vector2(prop_x, height * 0.58) - prop_size * Vector2(0.5, 0.72), prop_size),
                Color(0.72, 0.82, 0.70, 0.82),
            )
    draw_line(Vector2(0, height * 0.78), Vector2(width, height * 0.78), Color("f7e7ad"), 4)
    CombatFeedback.draw_attack_range(
        self,
        Vector2(170, 360),
        float(combat.get("attack_range", 300)),
        Color(0.25, 0.65, 1.0, 0.10),
        true,
        -1.0,
        false,
    )
    var pulse := absf(sin(elapsed * 7.0)) * 4.0
    var party_drawn := false
    if licensed_art_helper != null and licensed_art_texture != null:
        party_drawn = licensed_art_helper.draw_role(self, licensed_art_texture, licensed_art_manifest, "warrior", Rect2(100, 302, 74, 74))
        party_drawn = licensed_art_helper.draw_role(self, licensed_art_texture, licensed_art_manifest, "archer", Rect2(158, 322, 68, 68)) and party_drawn
        party_drawn = licensed_art_helper.draw_role(self, licensed_art_texture, licensed_art_manifest, "priest", Rect2(212, 300, 72, 72)) and party_drawn
    if not party_drawn:
        PresentationSkin.draw_side_scroll_party(self, Vector2(170, 350), pulse)
    var enemy_index := 0
    for enemy in enemies:
        var enemy_pos := Vector2(float(enemy["x"]), 360)
        var hp_ratio := clampf(float(enemy["hp"]) / float(combat["enemy_health"]), 0.0, 1.0)
        var enemy_role: String = ["enemy_scout", "enemy_brute", "enemy_beast", "enemy_caster"][enemy_index % 4]
        var enemy_drawn := false
        if licensed_art_helper != null and licensed_art_texture != null:
            enemy_drawn = licensed_art_helper.draw_role(self, licensed_art_texture, licensed_art_manifest, enemy_role, Rect2(enemy_pos - Vector2(34, 38), Vector2(68, 68)), Color(0.72, 1.0, 0.72, 1.0))
        if not enemy_drawn:
            PresentationSkin.draw_side_scroll_enemy(self, enemy_pos, hp_ratio, pulse)
        draw_rect(Rect2(enemy_pos.x - 24.0, enemy_pos.y - 49.0, 48.0, 5.0), Color("2a2430"), true)
        draw_rect(Rect2(enemy_pos.x - 22.0, enemy_pos.y - 47.0, 44.0 * hp_ratio, 2.0), Color("ff6558"), true)
        enemy_index += 1
    for effect in shot_effects:
        var effect_drawn := false
        if effect_player != null and effect_texture != null:
            var anchor: Vector2 = effect["from"] if String(effect["vfx_role"]) == "warrior_slash" else effect["to"]
            effect_drawn = effect_player.draw_effect(self, effect_texture, effect_manifest, String(effect["vfx_role"]), Rect2(anchor - Vector2(64, 64), Vector2(128, 128)), float(effect["ttl"]), float(effect["max_ttl"]))
        if not effect_drawn:
            CombatFeedback.draw_attack_line(
                self, effect["from"], effect["to"], Color("fff2a8"), 7.0, false
            )
    var ratio := progress_distance / maxf(1.0, float(destination.get("destination_distance", 1)))
    PresentationSkin.draw_hud_panel(self, Rect2(22, 16, width - 44, 100), Color("f1bd4a"))
    draw_rect(Rect2(36, 28, width - 72, 18), Color("27384a"), true)
    draw_rect(Rect2(39, 31, (width - 78) * ratio, 12), Color("f1bd4a"), true)
    var destination_drawn := false
    if licensed_art_helper != null and licensed_art_texture != null:
        destination_drawn = licensed_art_helper.draw_role(self, licensed_art_texture, licensed_art_manifest, "destination", Rect2(width - 145, 270, 132, 132))
    if not destination_drawn:
        PresentationSkin.draw_destination(self, Vector2(width - 75, 350), won)
    draw_string(ThemeDB.fallback_font, Vector2(36, 72), "AUTO MARCH  %d / %d m" % [int(progress_distance), int(destination.get("destination_distance", 0))], HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color("f4f0df"))
    draw_string(ThemeDB.fallback_font, Vector2(36, 102), "Kills %d   Auto attacks %d" % [total_kills, total_attacks], HORIZONTAL_ALIGNMENT_LEFT, -1, 19, Color("cfe4d9"))
    if won:
        draw_rect(Rect2(width * 0.25, height * 0.30, width * 0.50, 110), Color(0.08, 0.12, 0.18, 0.90), true)
        draw_string(ThemeDB.fallback_font, Vector2(width * 0.34, height * 0.40), "DESTINATION REACHED", HORIZONTAL_ALIGNMENT_LEFT, -1, 28, Color("fff0a4"))
'''


SIDE_SCROLL_PROBE_SCRIPT = r'''extends SceneTree

func _initialize() -> void:
    var output_path := "side-scroll-probe.json"
    for argument in OS.get_cmdline_user_args():
        if argument.begins_with("--output="):
            output_path = argument.trim_prefix("--output=")
    var scene = load("res://scenes/gameplay.tscn").instantiate()
    root.add_child(scene)
    await process_frame
    var initial_progress: float = scene.progress_distance
    scene.start_run()
    for index in range(400):
        scene.simulate_step(0.10)
    var receipt := {
        "schema_version": "khalinos-godot-side-scroll-probe-v1",
        "combat_feedback_pack_loaded": scene.COMBAT_FEEDBACK_PACK_ID == "godot.combat-feedback@1.0.0",
        "presentation_skin_pack_loaded": scene.PRESENTATION_SKIN_PACK_ID == "godot.presentation-skin@1.0.0",
        "audio_feedback_pack_loaded": scene.AUDIO_FEEDBACK_PACK_ID == "godot.audio-feedback@1.0.0",
        "licensed_art_requested": FileAccess.file_exists("res://KHALINOS_LICENSE_RECEIPT.json"),
        "licensed_art_loaded": scene.licensed_art_texture != null and scene.licensed_art_helper != null,
        "license_receipt_present": FileAccess.file_exists("res://KHALINOS_LICENSE_RECEIPT.json"),
        "effect_atlas_requested": FileAccess.file_exists("res://KHALINOS_EFFECT_RECEIPT.json"),
        "effect_atlas_loaded": scene.effect_texture != null and scene.effect_player != null,
        "effect_receipt_present": FileAccess.file_exists("res://KHALINOS_EFFECT_RECEIPT.json"),
        "effect_frame_animation_observed": (
            scene.effect_player == null
            or scene.effect_player.frame_region(scene.effect_manifest, "archer_impact", 0.45, 0.45)
            != scene.effect_player.frame_region(scene.effect_manifest, "archer_impact", 0.05, 0.45)
        ),
        "horizontal_lane_present": true,
        "movement_right": scene.progress_distance > initial_progress,
        "enemy_spawned": scene.total_spawned > 0,
        "auto_attack_fired": scene.total_attacks > 0,
        "enemy_defeated": scene.total_kills > 0,
        "destination_reached": scene.progress_distance >= float(scene.destination["destination_distance"]),
        "victory": scene.won,
        "progress_distance": scene.progress_distance,
        "spawned": scene.total_spawned,
        "attacks": scene.total_attacks,
        "kills": scene.total_kills,
        "attack_audio_events": int(scene.audio_events.get("attack", 0)),
        "hit_audio_events": int(scene.audio_events.get("hit", 0)),
        "victory_audio_events": int(scene.audio_events.get("victory", 0)),
    }
    receipt["passed"] = (
        receipt["combat_feedback_pack_loaded"]
        and receipt["presentation_skin_pack_loaded"] and receipt["audio_feedback_pack_loaded"]
        and receipt["movement_right"] and receipt["enemy_spawned"]
        and receipt["auto_attack_fired"] and receipt["enemy_defeated"]
        and receipt["destination_reached"] and receipt["victory"]
        and receipt["attack_audio_events"] > 0 and receipt["hit_audio_events"] > 0
        and receipt["victory_audio_events"] > 0
        and (not receipt["licensed_art_requested"] or (receipt["licensed_art_loaded"] and receipt["license_receipt_present"]))
        and (not receipt["effect_atlas_requested"] or (receipt["effect_atlas_loaded"] and receipt["effect_receipt_present"] and receipt["effect_frame_animation_observed"]))
    )
    var target := FileAccess.open(output_path, FileAccess.WRITE)
    target.store_string(JSON.stringify(receipt, "  ") + "\n")
    target.close()
    scene.queue_free()
    quit(0 if receipt["passed"] else 1)
'''


class GodotSideScrollPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-godot-side-scroll-plan-v1"] = "khalinos-godot-side-scroll-plan-v1"
    project_name: str = Field(min_length=3, max_length=80)
    viewport_width: int = Field(default=960, ge=640, le=1920)
    viewport_height: int = Field(default=540, ge=360, le=1080)
    destination_distance: float = Field(default=1000, ge=600, le=5000)
    party_speed: float = Field(default=90, ge=40, le=300)
    attack_damage: float = Field(default=24, ge=1, le=500)
    attack_interval: float = Field(default=0.55, ge=0.1, le=5)
    attack_range: float = Field(default=340, ge=80, le=500)
    enemy_health: float = Field(default=44, ge=1, le=1000)
    enemy_speed: float = Field(default=135, ge=10, le=300)
    enemy_spawn_interval: float = Field(default=1.8, ge=0.2, le=8)
    deterministic_seed: int = Field(default=73, ge=1, le=2_147_483_647)


class GodotSideScrollProjectPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-godot-side-scroll-project-plan-v1"] = (
        "khalinos-godot-side-scroll-project-plan-v1"
    )
    quest_plan: QuestPlan
    gameplay: GodotSideScrollPlan


class CompiledGodotSideScroll(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-compiled-godot-side-scroll-v1"] = "khalinos-compiled-godot-side-scroll-v1"
    plan: GodotSideScrollPlan
    concept: VisualConcept
    asset: ArtifactAsset
    licensed_art_atlas: ArtifactAsset | None = None
    effect_atlas: ArtifactAsset | None = None
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: dict[str, str] = Field(min_length=10, max_length=19)


GODOT_SIDE_SCROLL_LANE_COMBAT_PACK = CapabilityPackManifest(
    pack_id="godot.side-scroll-lane-combat",
    version="1.0.0",
    provides=("gameplay.auto-attack", "gameplay.side-scroll"),
    requires=("godot.project", "godot.visual.foundation"),
    conflicts=("gameplay.top-down",),
    text_paths=("KHALINOS_SIDE_SCROLL.json", "scripts/khalinos_side_scroll.gd"),
)
GODOT_DESTINATION_PROGRESSION_PACK = CapabilityPackManifest(
    pack_id="godot.destination-progression",
    version="1.0.0",
    provides=("gameplay.destination",),
    requires=("gameplay.side-scroll",),
    text_paths=("KHALINOS_DESTINATION.json",),
)
GODOT_SIDE_SCROLL_PROBE_PACK = CapabilityPackManifest(
    pack_id="godot.side-scroll-probe",
    version="1.0.0",
    provides=("evidence.side-scroll-probe",),
    requires=("audio.feedback", "gameplay.auto-attack", "gameplay.combat-feedback", "gameplay.destination", "gameplay.side-scroll", "godot.project", "presentation.skin"),
    text_paths=("scripts/khalinos_side_scroll_probe.gd",),
)
GODOT_SIDE_SCROLL_PROFILE = (
    GODOT_PROJECT_CORE_PACK,
    GODOT_VISUAL_FOUNDATION_PACK,
    GODOT_SIDE_SCROLL_LANE_COMBAT_PACK,
    GODOT_COMBAT_FEEDBACK_PACK,
    GODOT_PRESENTATION_SKIN_PACK,
    GODOT_AUDIO_FEEDBACK_PACK,
    GODOT_DESTINATION_PROGRESSION_PACK,
    GODOT_SIDE_SCROLL_PROBE_PACK,
)
GODOT_SIDE_SCROLL_LICENSED_ART_PROFILE = (
    GODOT_PROJECT_CORE_PACK,
    GODOT_VISUAL_FOUNDATION_PACK,
    GODOT_ASSET_SELECTOR_PACK,
    GODOT_STYLE_COMPOSER_PACK,
    GODOT_LICENSED_ATLAS_PACK,
    GODOT_LICENSE_RECEIPT_PACK,
    GODOT_SIDE_SCROLL_LANE_COMBAT_PACK,
    GODOT_COMBAT_FEEDBACK_PACK,
    GODOT_PRESENTATION_SKIN_PACK,
    GODOT_AUDIO_FEEDBACK_PACK,
    GODOT_DESTINATION_PROGRESSION_PACK,
    GODOT_SIDE_SCROLL_PROBE_PACK,
)
GODOT_SIDE_SCROLL_EFFECT_PACKS = (
    GODOT_EFFECT_SELECTOR_PACK,
    GODOT_EFFECT_ATLAS_PACK,
    GODOT_VFX_PLAYER_PACK,
    GODOT_EFFECT_RECEIPT_PACK,
)
GODOT_SIDE_SCROLL_VFX_PROFILE = (
    GODOT_SIDE_SCROLL_PROFILE[:-2]
    + GODOT_SIDE_SCROLL_EFFECT_PACKS
    + GODOT_SIDE_SCROLL_PROFILE[-2:]
)
GODOT_SIDE_SCROLL_LICENSED_ART_VFX_PROFILE = (
    GODOT_SIDE_SCROLL_LICENSED_ART_PROFILE[:-2]
    + GODOT_SIDE_SCROLL_EFFECT_PACKS
    + (GODOT_DESTINATION_PROGRESSION_PACK, GODOT_SIDE_SCROLL_PROBE_PACK)
)


def _sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compose_godot_side_scroll_capabilities(
    plan: GodotSideScrollPlan,
    licensed_art: LicensedArtBundle | None = None,
    effects: EffectBundle | None = None,
) -> CapabilityComposition:
    combat_manifest = {
        "schema_version": plan.schema_version,
        "viewport_width": plan.viewport_width,
        "viewport_height": plan.viewport_height,
        "attack_damage": plan.attack_damage,
        "attack_interval": plan.attack_interval,
        "attack_range": plan.attack_range,
        "enemy_health": plan.enemy_health,
        "enemy_speed": plan.enemy_speed,
        "enemy_spawn_interval": plan.enemy_spawn_interval,
        "deterministic_seed": plan.deterministic_seed,
    }
    destination_manifest = {
        "schema_version": "khalinos-godot-destination-v1",
        "destination_distance": plan.destination_distance,
        "party_speed": plan.party_speed,
    }
    stages = [
        godot_project_core_stage(
            project_name=plan.project_name,
            viewport_width=plan.viewport_width,
            viewport_height=plan.viewport_height,
            readme_body="A bounded side-scrolling auto-combat journey composed by KHALINOS.\n\nThe party advances from left to right, attacks approaching enemies automatically, and wins by reaching the destination flag.",
        ),
        godot_visual_foundation_stage(
            viewport_width=plan.viewport_width,
            viewport_height=plan.viewport_height,
            script_path="scripts/khalinos_side_scroll.gd",
            node_name="SideScrollJourney",
        ),
    ]
    if licensed_art is not None:
        if licensed_art.profile_id != "godot.side-scroll-destination":
            raise PermissionError("side-scroll profile received licensed art for another profile")
        stages.extend(godot_licensed_art_stages(licensed_art))
    stages.extend((
        CapabilityPackStage(
            manifest=GODOT_SIDE_SCROLL_LANE_COMBAT_PACK,
            text_files={
                "KHALINOS_SIDE_SCROLL.json": json.dumps(combat_manifest, ensure_ascii=False, indent=2) + "\n",
                "scripts/khalinos_side_scroll.gd": SIDE_SCROLL_SCRIPT,
            },
        ),
        godot_combat_feedback_stage(),
        godot_presentation_skin_stage(),
        godot_audio_feedback_stage(),
    ))
    if effects is not None:
        if effects.profile_id != "godot.side-scroll-destination":
            raise PermissionError("side-scroll profile received effects for another profile")
        stages.extend(godot_effect_stages(effects))
    stages.extend((
        CapabilityPackStage(
            manifest=GODOT_DESTINATION_PROGRESSION_PACK,
            text_files={
                "KHALINOS_DESTINATION.json": json.dumps(destination_manifest, ensure_ascii=False, indent=2) + "\n",
            },
        ),
        CapabilityPackStage(
            manifest=GODOT_SIDE_SCROLL_PROBE_PACK,
            text_files={"scripts/khalinos_side_scroll_probe.gd": SIDE_SCROLL_PROBE_SCRIPT},
        ),
    ))
    return compose_capability_stages(stages)


def compile_godot_side_scroll(
    plan: GodotSideScrollPlan,
    concept: VisualConcept,
    asset: ArtifactAsset,
    licensed_art: LicensedArtBundle | None = None,
    effects: EffectBundle | None = None,
) -> CompiledGodotSideScroll:
    if asset.path != ASSET_PATH or asset.media_type != "image/png":
        raise ValueError("Godot side-scroll profile requires the trusted visual foundation PNG")
    composition = compose_godot_side_scroll_capabilities(plan, licensed_art, effects)
    expected_binary_paths = {ASSET_PATH} | ({LICENSED_ATLAS_PATH} if licensed_art is not None else set()) | ({EFFECT_ATLAS_PATH} if effects is not None else set())
    if set(composition.binary_paths) != expected_binary_paths:
        raise PermissionError("Godot side-scroll binary bindings do not match approved assets")
    files = {
        path: content.replace("\r\n", "\n").replace("\r", "\n")
        for path, content in composition.text_files.items()
    }
    plan_sha = _sha256({
        "plan": plan.model_dump(mode="json"),
        "concept": concept.model_dump(mode="json"),
        "asset_sha256": asset.sha256,
        "licensed_art_sha256": licensed_art.atlas.sha256 if licensed_art else None,
        "effect_atlas_sha256": effects.atlas.sha256 if effects else None,
    })
    return CompiledGodotSideScroll(
        plan=plan,
        concept=concept,
        asset=asset,
        licensed_art_atlas=licensed_art.atlas if licensed_art else None,
        effect_atlas=effects.atlas if effects else None,
        plan_sha256=plan_sha,
        bundle_sha256=_sha256({
            "plan_sha256": plan_sha,
            "files": files,
            "asset_sha256": asset.sha256,
            "licensed_art_sha256": licensed_art.atlas.sha256 if licensed_art else None,
            "effect_atlas_sha256": effects.atlas.sha256 if effects else None,
        }),
        files=files,
    )
