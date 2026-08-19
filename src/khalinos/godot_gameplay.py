"""Trusted compiler for bounded, data-driven Godot 2D gameplay vertical slices."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from khalinos.models import ArtifactAsset, QuestPlan, VisualConcept
from khalinos.visual_assets import ASSET_PATH


def _sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GameplayAbilityKind(StrEnum):
    DAMAGE = "damage"
    HEAL = "heal"
    SHIELD = "shield"
    BUFF = "buff"


class GameplayHero(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hero_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    label: str = Field(min_length=1, max_length=40)
    role: Literal["tank", "damage", "support", "hybrid"]
    color_hex: str = Field(pattern=r"^[A-Fa-f0-9]{6}$")
    health: int = Field(ge=20, le=10_000)
    attack: int = Field(ge=1, le=2_000)
    defense: int = Field(ge=0, le=2_000)
    move_speed: float = Field(ge=40, le=800)


class GameplayEnemy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enemy_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    label: str = Field(min_length=1, max_length=40)
    color_hex: str = Field(pattern=r"^[A-Fa-f0-9]{6}$")
    health: int = Field(ge=1, le=20_000)
    damage: int = Field(ge=1, le=2_000)
    speed: float = Field(ge=10, le=500)
    record_value: int = Field(ge=1, le=1_000)
    spawn_weight: int = Field(ge=1, le=100)


class GameplayAbility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ability_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    label: str = Field(min_length=1, max_length=50)
    owner_hero_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    kind: GameplayAbilityKind
    cooldown_seconds: float = Field(ge=0.25, le=300)
    power: int = Field(ge=1, le=10_000)
    radius: float = Field(ge=20, le=1_000)


class GodotGameplayPlan(BaseModel):
    """The only model-authored gameplay contract accepted by the trusted compiler."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-godot-gameplay-plan-v1"] = "khalinos-godot-gameplay-plan-v1"
    project_name: str = Field(min_length=2, max_length=80)
    genre: Literal["top_down_survival", "top_down_action"] = "top_down_survival"
    viewport_width: int = Field(default=1280, ge=640, le=1920)
    viewport_height: int = Field(default=720, ge=360, le=1080)
    session_seconds: int = Field(ge=30, le=1200)
    heroes: tuple[GameplayHero, ...] = Field(min_length=1, max_length=4)
    enemies: tuple[GameplayEnemy, ...] = Field(min_length=1, max_length=8)
    abilities: tuple[GameplayAbility, ...] = Field(min_length=1, max_length=16)
    level_count: int = Field(ge=2, le=20)
    level_interval_seconds: int = Field(ge=5, le=180)
    choices_per_level: int = Field(ge=2, le=5)
    deterministic_seed: int = Field(ge=1, le=2_147_483_647)

    @model_validator(mode="after")
    def validate_references(self) -> "GodotGameplayPlan":
        hero_ids = [item.hero_id for item in self.heroes]
        enemy_ids = [item.enemy_id for item in self.enemies]
        ability_ids = [item.ability_id for item in self.abilities]
        for label, values in (("hero", hero_ids), ("enemy", enemy_ids), ("ability", ability_ids)):
            if len(values) != len(set(values)):
                raise ValueError(f"Godot gameplay {label} IDs must be unique")
        unknown = {item.owner_hero_id for item in self.abilities} - set(hero_ids)
        if unknown:
            raise ValueError(f"Godot gameplay abilities reference unknown heroes: {sorted(unknown)}")
        if self.level_interval_seconds * (self.level_count - 1) > self.session_seconds:
            raise ValueError("Godot gameplay level schedule exceeds the session duration")
        return self


class GodotGameplayProjectPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-godot-gameplay-project-plan-v1"] = "khalinos-godot-gameplay-project-plan-v1"
    quest_plan: QuestPlan
    gameplay: GodotGameplayPlan


class CompiledGodotGameplay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-compiled-godot-gameplay-v1"] = "khalinos-compiled-godot-gameplay-v1"
    gameplay: GodotGameplayPlan
    concept: VisualConcept
    asset: ArtifactAsset
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: dict[str, str] = Field(min_length=6, max_length=12)


GAMEPLAY_SCRIPT = r'''extends Node2D

var config: Dictionary
var center := Vector2.ZERO
var shared_health := 0.0
var shared_health_max := 0.0
var shield := 0.0
var elapsed := 0.0
var spawn_clock := 0.0
var level := 1
var records := 0
var enemies: Array[Dictionary] = []
var ability_clocks: Dictionary = {}
var choice_open := false
var ended := false
var victory := false
var rng := RandomNumberGenerator.new()

func _ready() -> void:
    config = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_GAMEPLAY.json"))
    center = Vector2(config.viewport_width / 2.0, config.viewport_height / 2.0)
    for hero in config.heroes:
        shared_health_max += float(hero.health)
    shared_health = shared_health_max
    for ability in config.abilities:
        ability_clocks[ability.ability_id] = 0.0
    rng.seed = int(config.deterministic_seed)
    queue_redraw()

func _process(delta: float) -> void:
    if ended or choice_open:
        return
    var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")
    _step_simulation(delta, direction)
    queue_redraw()

func _unhandled_key_input(event: InputEvent) -> void:
    if event.is_pressed() and choice_open and event.keycode >= KEY_1 and event.keycode <= KEY_5:
        _choose_upgrade(int(event.keycode - KEY_1))
    elif event.is_pressed() and ended and event.keycode == KEY_R:
        get_tree().reload_current_scene()

func _step_simulation(delta: float, direction: Vector2) -> void:
    elapsed += delta
    var speed := 0.0
    for hero in config.heroes:
        speed += float(hero.move_speed)
    speed /= max(1, config.heroes.size())
    center += direction.normalized() * speed * delta
    center.x = clamp(center.x, 70.0, float(config.viewport_width) - 70.0)
    center.y = clamp(center.y, 90.0, float(config.viewport_height) - 70.0)
    spawn_clock += delta
    var spawn_interval: float = max(0.35, 1.6 - elapsed / max(30.0, float(config.session_seconds)))
    while spawn_clock >= spawn_interval:
        spawn_clock -= spawn_interval
        _spawn_enemy()
    for enemy in enemies:
        var offset: Vector2 = center - enemy.position
        if offset.length() > 1.0:
            enemy.position += offset.normalized() * float(enemy.speed) * delta
        if offset.length() < 36.0:
            _apply_damage(max(1.0, float(enemy.damage) * delta - _party_defense() * 0.01 * delta))
    _tick_abilities(delta)
    _remove_dead()
    var target_level: int = min(int(config.level_count), 1 + int(elapsed / float(config.level_interval_seconds)))
    if target_level > level:
        choice_open = true
    if shared_health <= 0.0:
        ended = true
        victory = false
    elif elapsed >= float(config.session_seconds):
        ended = true
        victory = true

func _party_defense() -> float:
    var value := 0.0
    for hero in config.heroes:
        value += float(hero.defense)
    return value

func _spawn_enemy() -> void:
    var template: Dictionary = config.enemies[rng.randi_range(0, config.enemies.size() - 1)]
    var angle: float = rng.randf_range(0.0, TAU)
    var distance: float = float(max(int(config.viewport_width), int(config.viewport_height))) * 0.55
    enemies.append({
        "enemy_id": template.enemy_id,
        "position": center + Vector2.from_angle(angle) * distance,
        "health": float(template.health) * (1.0 + elapsed / max(60.0, float(config.session_seconds))),
        "damage": template.damage,
        "speed": template.speed,
        "record_value": template.record_value,
        "color_hex": template.color_hex,
    })

func _tick_abilities(delta: float) -> void:
    for ability in config.abilities:
        var id: String = ability.ability_id
        ability_clocks[id] = float(ability_clocks[id]) + delta
        if float(ability_clocks[id]) < float(ability.cooldown_seconds):
            continue
        ability_clocks[id] = 0.0
        match ability.kind:
            "damage":
                for enemy in enemies:
                    if enemy.position.distance_to(center) <= float(ability.radius):
                        enemy.health -= float(ability.power)
            "heal":
                shared_health = min(shared_health_max, shared_health + float(ability.power))
            "shield":
                shield = max(shield, float(ability.power))
            "buff":
                for enemy in enemies:
                    enemy.health -= float(ability.power) * 0.25

func _apply_damage(amount: float) -> void:
    var absorbed: float = min(shield, amount)
    shield -= absorbed
    shared_health -= amount - absorbed

func _remove_dead() -> void:
    var alive: Array[Dictionary] = []
    for enemy in enemies:
        if float(enemy.health) <= 0.0:
            records += int(enemy.record_value)
        else:
            alive.append(enemy)
    enemies = alive

func _choose_upgrade(index: int) -> void:
    if index < 0 or index >= int(config.choices_per_level):
        return
    level = min(int(config.level_count), level + 1)
    shared_health_max *= 1.08
    shared_health = min(shared_health_max, shared_health + shared_health_max * 0.12)
    choice_open = false

func verification_scenario() -> Dictionary:
    var start := center
    _step_simulation(0.5, Vector2.RIGHT)
    var moved := center.x > start.x
    _spawn_enemy()
    var spawned := enemies.size() > 0
    for enemy in enemies:
        enemy.position = center
        enemy.health = 1.0
    for ability in config.abilities:
        ability_clocks[ability.ability_id] = float(ability.cooldown_seconds)
    _tick_abilities(0.01)
    _remove_dead()
    var ability_applied := records > 0 or shared_health > 0.0 or shield > 0.0
    elapsed = float(config.level_interval_seconds)
    _step_simulation(0.01, Vector2.ZERO)
    var offered := choice_open
    _choose_upgrade(0)
    var upgraded := level == 2 and not choice_open
    return {
        "schema_version": "khalinos-godot-gameplay-probe-v1",
        "formation_count": config.heroes.size(),
        "movement_applied": moved,
        "enemy_spawned": spawned,
        "auto_ability_applied": ability_applied,
        "shared_health_initialized": shared_health_max > 0.0,
        "level_choice_offered": offered,
        "level_choice_applied": upgraded,
        "seed": config.deterministic_seed,
    }

func _draw() -> void:
    draw_rect(Rect2(Vector2.ZERO, Vector2(config.viewport_width, config.viewport_height)), Color(0.09, 0.15, 0.12, 0.82))
    for x in range(0, int(config.viewport_width), 64):
        draw_line(Vector2(x, 0), Vector2(x, config.viewport_height), Color(0.3, 0.5, 0.32, 0.15), 1.0)
    for y in range(0, int(config.viewport_height), 64):
        draw_line(Vector2(0, y), Vector2(config.viewport_width, y), Color(0.3, 0.5, 0.32, 0.15), 1.0)
    var hero_index := 0
    for hero in config.heroes:
        var angle: float = TAU * float(hero_index) / max(1.0, float(config.heroes.size())) - PI / 2.0
        var position: Vector2 = center + Vector2.from_angle(angle) * 30.0
        draw_circle(position, 16.0, Color(hero.color_hex))
        draw_circle(position, 18.0, Color("f3e6bd"), false, 3.0)
        hero_index += 1
    for enemy in enemies:
        draw_circle(enemy.position, 12.0, Color(enemy.color_hex))
    draw_rect(Rect2(28, 24, 360, 22), Color(0.08, 0.09, 0.08, 0.9))
    draw_rect(Rect2(31, 27, 354.0 * clamp(shared_health / max(1.0, shared_health_max), 0.0, 1.0), 16), Color("b84a3a"))
    if choice_open:
        draw_rect(Rect2(config.viewport_width / 2.0 - 280, config.viewport_height / 2.0 - 120, 560, 240), Color(0.08, 0.1, 0.08, 0.95))

'''


PROBE_SCRIPT = r'''extends SceneTree

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
    var packed = load("res://scenes/gameplay.tscn")
    var instance = packed.instantiate() if packed != null else null
    if instance != null:
        root.add_child(instance)
        await process_frame
    var receipt: Dictionary = instance.verification_scenario() if instance != null else {}
    receipt.passed = (
        receipt.get("movement_applied", false)
        and receipt.get("enemy_spawned", false)
        and receipt.get("auto_ability_applied", false)
        and receipt.get("shared_health_initialized", false)
        and receipt.get("level_choice_offered", false)
        and receipt.get("level_choice_applied", false)
    )
    var target := FileAccess.open(output, FileAccess.WRITE)
    target.store_string(JSON.stringify(receipt))
    target.close()
    if instance != null:
        instance.queue_free()
    quit(0 if receipt.passed else 1)
'''


def _scene(width: int, height: int) -> str:
    return f'''[gd_scene load_steps=3 format=3]\n\n[ext_resource type="Script" path="res://scripts/khalinos_gameplay.gd" id="1"]\n[ext_resource type="Texture2D" path="res://assets/visual-foundation.png" id="2"]\n\n[node name="Gameplay" type="Node2D"]\nscript = ExtResource("1")\n\n[node name="VisualFoundation" type="TextureRect" parent="."]\noffset_right = {float(width):.1f}\noffset_bottom = {float(height):.1f}\ntexture = ExtResource("2")\nexpand_mode = 1\nstretch_mode = 6\nmouse_filter = 2\nmodulate = Color(1, 1, 1, 0.42)\nz_index = -2\n'''


def compile_godot_gameplay(
    plan: GodotGameplayPlan,
    concept: VisualConcept,
    asset: ArtifactAsset,
) -> CompiledGodotGameplay:
    if asset.path != ASSET_PATH or asset.media_type != "image/png":
        raise ValueError("Godot gameplay requires the trusted visual foundation PNG")
    safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "", plan.project_name).strip() or "KHALINOS Game"
    manifest = plan.model_dump(mode="json")
    plan_sha = _sha256({"gameplay": manifest, "concept": concept.model_dump(mode="json"), "asset_sha256": asset.sha256})
    files = {
        "project.godot": f'''[application]\nconfig/name={json.dumps(safe_name)}\nrun/main_scene="res://scenes/gameplay.tscn"\n\n[display]\nwindow/size/viewport_width={plan.viewport_width}\nwindow/size/viewport_height={plan.viewport_height}\nwindow/size/window_width_override={plan.viewport_width}\nwindow/size/window_height_override={plan.viewport_height}\n\n[input]\nmove_left={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":65), Object(InputEventKey,"physical_keycode":4194311)]}}\nmove_right={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":68), Object(InputEventKey,"physical_keycode":4194313)]}}\nmove_up={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":87), Object(InputEventKey,"physical_keycode":4194320)]}}\nmove_down={{"deadzone": 0.5, "events": [Object(InputEventKey,"physical_keycode":83), Object(InputEventKey,"physical_keycode":4194322)]}}\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\nrenderer/rendering_method.mobile="gl_compatibility"\n''',
        "scenes/gameplay.tscn": _scene(plan.viewport_width, plan.viewport_height),
        "scripts/khalinos_gameplay.gd": GAMEPLAY_SCRIPT,
        "scripts/khalinos_gameplay_probe.gd": PROBE_SCRIPT,
        "KHALINOS_GAMEPLAY.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        "README.md": f"# {safe_name}\n\nA bounded Godot 2D gameplay vertical slice generated by the KHALINOS Godot Gameplay ToolPack.\n\nMove with WASD or arrow keys. Choose level upgrades with number keys. Press R after victory or defeat to restart.\n",
    }
    files = {path: content.replace("\r\n", "\n").replace("\r", "\n") for path, content in files.items()}
    return CompiledGodotGameplay(
        gameplay=plan,
        concept=concept,
        asset=asset,
        plan_sha256=plan_sha,
        bundle_sha256=_sha256({"plan_sha256": plan_sha, "files": files, "asset_sha256": asset.sha256}),
        files=files,
    )
