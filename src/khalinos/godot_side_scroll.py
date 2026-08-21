"""Bounded side-scrolling auto-combat profile composed from Godot Capability Packs."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from khalinos.godot_capability_packs import (
    GODOT_COMBAT_FEEDBACK_PACK,
    GODOT_PROJECT_CORE_PACK,
    GODOT_VISUAL_FOUNDATION_PACK,
    godot_combat_feedback_stage,
    godot_project_core_stage,
    godot_visual_foundation_stage,
)
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
const COMBAT_FEEDBACK_PACK_ID := CombatFeedback.PACK_ID

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

func _ready() -> void:
    combat = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_SIDE_SCROLL.json"))
    destination = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_DESTINATION.json"))
    queue_redraw()

func start_run() -> void:
    started = true

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
            shot_effects.append({"from": Vector2(190, 360), "to": Vector2(float(target["x"]), 360), "ttl": 0.22})
            if float(target["hp"]) <= 0.0:
                enemies.erase(target)
                total_kills += 1
    for effect in shot_effects.duplicate():
        effect["ttl"] = float(effect["ttl"]) - delta
        if float(effect["ttl"]) <= 0.0:
            shot_effects.erase(effect)
    if progress_distance >= float(destination["destination_distance"]):
        won = true

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
    draw_rect(Rect2(0, 0, width, height), Color("bde6ef"), true)
    draw_rect(Rect2(0, height * 0.58, width, height * 0.42), Color("d6c58b"), true)
    draw_rect(Rect2(0, height * 0.72, width, height * 0.12), Color("907d57"), true)
    for index in range(7):
        var offset := fmod(float(index * 180) - progress_distance * 0.35, width + 180.0) - 90.0
        draw_circle(Vector2(offset, height * 0.53), 48, Color("79aa68"))
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
    draw_circle(Vector2(150, 342), 22, Color("d69a43"))
    draw_circle(Vector2(170, 376), 19, Color("5b86c4"))
    draw_circle(Vector2(188, 338), 17, Color("eadf8b"))
    for enemy in enemies:
        var enemy_pos := Vector2(float(enemy["x"]), 360)
        draw_rect(Rect2(enemy_pos.x - 20, enemy_pos.y - 25, 40, 50), Color("398b45"), true)
        draw_circle(enemy_pos + Vector2(0, -25), 17, Color("65bd54"))
        draw_rect(Rect2(enemy_pos.x - 22, enemy_pos.y - 48, 44, 5), Color("3b2634"), true)
        var hp_ratio := clampf(float(enemy["hp"]) / float(combat["enemy_health"]), 0.0, 1.0)
        draw_rect(Rect2(enemy_pos.x - 22, enemy_pos.y - 48, 44 * hp_ratio, 5), Color("e85b4f"), true)
    for effect in shot_effects:
        CombatFeedback.draw_attack_line(
            self, effect["from"], effect["to"], Color("fff2a8"), 7.0, false
        )
    var ratio := progress_distance / maxf(1.0, float(destination.get("destination_distance", 1)))
    draw_rect(Rect2(36, 28, width - 72, 18), Color("27384a"), true)
    draw_rect(Rect2(39, 31, (width - 78) * ratio, 12), Color("f1bd4a"), true)
    draw_line(Vector2(width - 75, 300), Vector2(width - 75, 390), Color("faf5d8"), 7)
    draw_colored_polygon(PackedVector2Array([
        Vector2(width - 72, 302), Vector2(width - 18, 320), Vector2(width - 72, 338)
    ]), Color("d94b45"))
    draw_string(ThemeDB.fallback_font, Vector2(36, 72), "AUTO MARCH  %d / %d m" % [int(progress_distance), int(destination.get("destination_distance", 0))], HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color("18293a"))
    draw_string(ThemeDB.fallback_font, Vector2(36, 102), "Kills %d   Auto attacks %d" % [total_kills, total_attacks], HORIZONTAL_ALIGNMENT_LEFT, -1, 19, Color("23384a"))
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
    }
    receipt["passed"] = (
        receipt["combat_feedback_pack_loaded"]
        and receipt["movement_right"] and receipt["enemy_spawned"]
        and receipt["auto_attack_fired"] and receipt["enemy_defeated"]
        and receipt["destination_reached"] and receipt["victory"]
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
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: dict[str, str] = Field(min_length=8, max_length=8)


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
    requires=("gameplay.auto-attack", "gameplay.combat-feedback", "gameplay.destination", "gameplay.side-scroll", "godot.project"),
    text_paths=("scripts/khalinos_side_scroll_probe.gd",),
)
GODOT_SIDE_SCROLL_PROFILE = (
    GODOT_PROJECT_CORE_PACK,
    GODOT_VISUAL_FOUNDATION_PACK,
    GODOT_SIDE_SCROLL_LANE_COMBAT_PACK,
    GODOT_COMBAT_FEEDBACK_PACK,
    GODOT_DESTINATION_PROGRESSION_PACK,
    GODOT_SIDE_SCROLL_PROBE_PACK,
)


def _sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compose_godot_side_scroll_capabilities(plan: GodotSideScrollPlan) -> CapabilityComposition:
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
    return compose_capability_stages((
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
        CapabilityPackStage(
            manifest=GODOT_SIDE_SCROLL_LANE_COMBAT_PACK,
            text_files={
                "KHALINOS_SIDE_SCROLL.json": json.dumps(combat_manifest, ensure_ascii=False, indent=2) + "\n",
                "scripts/khalinos_side_scroll.gd": SIDE_SCROLL_SCRIPT,
            },
        ),
        godot_combat_feedback_stage(),
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


def compile_godot_side_scroll(
    plan: GodotSideScrollPlan,
    concept: VisualConcept,
    asset: ArtifactAsset,
) -> CompiledGodotSideScroll:
    if asset.path != ASSET_PATH or asset.media_type != "image/png":
        raise ValueError("Godot side-scroll profile requires the trusted visual foundation PNG")
    composition = compose_godot_side_scroll_capabilities(plan)
    if composition.binary_paths != (ASSET_PATH,):
        raise PermissionError("Godot side-scroll binary bindings do not match approved assets")
    files = {
        path: content.replace("\r\n", "\n").replace("\r", "\n")
        for path, content in composition.text_files.items()
    }
    plan_sha = _sha256({
        "plan": plan.model_dump(mode="json"),
        "concept": concept.model_dump(mode="json"),
        "asset_sha256": asset.sha256,
    })
    return CompiledGodotSideScroll(
        plan=plan,
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
