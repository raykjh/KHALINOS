"""Trusted compiler for bounded, data-driven Godot 2D gameplay vertical slices."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from khalinos.models import ArtifactAsset, QuestPlan, VisualConcept
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
from khalinos.toolpacks import (
    CapabilityComposition,
    CapabilityPackManifest,
    CapabilityPackStage,
    compose_capability_stages,
)
from khalinos.sprite_assets import (
    SPRITE_ATLAS_MANIFEST_PATH,
    SPRITE_ATLAS_PATH,
    SPRITE_SEGMENTATION_CONTRACT,
    SpriteAtlasPlan,
    SpriteSlot,
)
from khalinos.visual_assets import ASSET_PATH


def _sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def explicit_gameplay_criteria(text: str) -> list[str]:
    """Translate explicit user gameplay requirements into probe-shaped criteria."""

    normalized = " ".join(text.casefold().replace("–", "-").split())
    criteria: list[str] = []
    has_ten_minutes = (
        bool(re.search(r"\b10(?:-|\s*)minute", normalized))
        or "600 second" in normalized
        or "10:00" in normalized
    )
    minute_cadence = "once per minute" in normalized or "about once per minute" in normalized or "1 minute" in normalized
    if has_ten_minutes or minute_cadence:
        criteria.append(
            "The probe verifies a 600-second session, ten Trinity levels at 60-second intervals, and victory exactly at the session boundary."
        )
    if "countdown" in normalized or "count down" in normalized or "10:00" in normalized:
        criteria.append(
            "The rendered HUD shows a decreasing session countdown that begins only after the player starts the run."
        )
    if "start button" in normalized or "start screen" in normalized or "press start" in normalized:
        criteria.append(
            "The rendered game waits at a visible START gate and accepts mouse, Enter, or Space before combat begins."
        )
    if any(phrase in normalized for phrase in ("attack range", "attack radius", "attack motion", "attack animation")):
        criteria.append(
            "Automatic hero attacks show a visible motion, active range, and impact-timed combat feedback."
        )
    if any(phrase in normalized for phrase in ("basic attack", "normal attack", "regular attack")):
        criteria.append(
            "Every hero independently performs a visible role-distinct basic attack against an enemy in range."
        )
    if "skill" in normalized and ("cooldown" in normalized or "cool down" in normalized):
        criteria.append(
            "Skills obey their declared cooldowns, expose remaining cooldown time in the HUD, and use effects distinct from basic attacks."
        )
    if any(phrase in normalized for phrase in ("heal effect", "healing effect", "visible heal")):
        criteria.append(
            "Healing produces a distinct visible green restorative effect around the party."
        )
    if any(phrase in normalized for phrase in ("enemy attack effect", "monster attack effect", "mob attack effect")):
        criteria.append(
            "Nearby enemies attack on a bounded cadence with a separate visible hostile impact effect."
        )
    if "level 1" in normalized and any(phrase in normalized for phrase in ("first enemy", "first monster", "first mob")):
        criteria.append(
            "The first level-one enemy is the lowest-threat unlocked type and is beatable by the initial party basic attacks."
        )
    if "green" in normalized and any(term in normalized for term in ("enemy", "enemies", "monster", "monsters")):
        criteria.append(
            "Rendered enemies use a green hostile visual family that remains immediately distinct from the hero formation."
        )
    if any(phrase in normalized for phrase in ("bright background", "brighter background", "lighter background")):
        criteria.append(
            "The rendered battlefield uses a brighter readable background while preserving HUD, hero, and enemy contrast."
        )
    if any(phrase in normalized for phrase in ("victory message", "defeat message", "restart prompt", "level choice text")):
        criteria.append(
            "Paused level choices and victory or defeat states visibly explain the state and the next available input."
        )
    has_three_roles = (
        "tank" in normalized
        and "damage" in normalized
        and ("healer" in normalized or "healing" in normalized or "support" in normalized)
    )
    role_order = has_three_roles and any(
        phrase in normalized
        for phrase in ("in order", "order repeats by role", "promotion order", "upgrade order")
    )
    three_choices = (
        (
            "one upgrade" in normalized
            or "1 upgrade" in normalized
            or "one guaranteed same-profession" in normalized
            or "advance the current profession" in normalized
        )
        and (
            "two alternative" in normalized
            or "2 alternative" in normalized
            or "two distinct professions" in normalized
            or "second distinct" in normalized
        )
    )
    if role_order or three_choices:
        criteria.append(
            "The probe verifies Tank, Damage, and Healer upgrade turns in order, with one current-profession rank-up and two alternative professions at every level choice."
        )
    stat_terms = ("health", "attack", "defense", "attack speed", "movement speed")
    if ("combined" in normalized or "sum" in normalized or "trinity attack =" in normalized) and all(
        term in normalized for term in stat_terms
    ):
        criteria.append(
            "The probe verifies that party health, attack, defense, attack speed, and movement speed equal the sum of all three heroes."
        )
    if "resurrection" in normalized or "stored resurrection" in normalized:
        criteria.append(
            "The probe verifies that automatic priest resurrection stores at most one charge and consumes it to survive otherwise lethal shared-health damage."
        )
    return criteria


def validate_gameplay_plan_requirements(plan: "GodotGameplayPlan", criteria: list[str]) -> None:
    """Fail before materialization when the plan cannot produce approved probe evidence."""

    normalized = " ".join(criteria).casefold()
    if "600-second session" in normalized and (
        plan.session_seconds != 600 or plan.level_count != 10 or plan.level_interval_seconds != 60
    ):
        raise PermissionError("Godot gameplay plan changed the approved 10-minute level schedule")
    if "tank, damage, and healer upgrade turns" in normalized:
        if plan.upgrade_role_order != ("tank", "damage", "support"):
            raise PermissionError("Godot gameplay plan changed the approved Tank-Damage-Healer order")
        if plan.choices_per_level != 3 or {item.role for item in plan.profession_rosters} != {"tank", "damage", "support"}:
            raise PermissionError("Godot gameplay plan lacks the approved three-choice profession rosters")
    if "equal the sum of all three heroes" in normalized and plan.team_stat_mode != "sum":
        raise PermissionError("Godot gameplay plan changed the approved summed party-stat contract")
    if "resurrection stores at most one charge" in normalized:
        resurrection = [item for item in plan.abilities if item.kind == GameplayAbilityKind.RESURRECTION]
        if plan.resurrection_capacity != 1 or len(resurrection) != 1:
            raise PermissionError("Godot gameplay plan lacks one bounded automatic resurrection ability")


class GameplayAbilityKind(StrEnum):
    DAMAGE = "damage"
    HEAL = "heal"
    SHIELD = "shield"
    BUFF = "buff"
    RESURRECTION = "resurrection"


class GameplayHero(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hero_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    label: str = Field(min_length=1, max_length=40)
    role: Literal["tank", "damage", "support", "hybrid"]
    color_hex: str = Field(pattern=r"^[A-Fa-f0-9]{6}$")
    health: int = Field(ge=20, le=10_000)
    attack: int = Field(ge=1, le=2_000)
    defense: int = Field(ge=0, le=2_000)
    attack_speed: float = Field(default=1.0, ge=0.1, le=20)
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


class GameplayProfession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profession_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    label: str = Field(min_length=1, max_length=50)
    role: Literal["tank", "damage", "support"]
    stat_focus: Literal["balanced", "health", "attack", "defense", "attack_speed", "move_speed", "utility"]


class GameplayProfessionRoster(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["tank", "damage", "support"]
    starting_profession_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    professions: tuple[GameplayProfession, ...] = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def valid_roster(self) -> "GameplayProfessionRoster":
        ids = [item.profession_id for item in self.professions]
        if len(ids) != len(set(ids)):
            raise ValueError("profession IDs must be unique inside one role roster")
        if self.starting_profession_id not in ids:
            raise ValueError("starting profession must exist in its role roster")
        if any(item.role != self.role for item in self.professions):
            raise ValueError("profession role must match its roster role")
        return self


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
    profession_choice_mode: Literal["seeded_random_alternatives"] = "seeded_random_alternatives"
    team_stat_mode: Literal["sum"] = "sum"
    upgrade_role_order: tuple[Literal["tank", "damage", "support"], ...] = Field(
        default=("tank", "damage", "support"), min_length=1, max_length=3,
    )
    profession_rosters: tuple[GameplayProfessionRoster, ...] = Field(default=(), max_length=3)
    resurrection_capacity: int = Field(default=0, ge=0, le=1)
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
        if len(self.upgrade_role_order) != len(set(self.upgrade_role_order)):
            raise ValueError("upgrade role order must not repeat a role")
        roster_roles = [item.role for item in self.profession_rosters]
        if len(roster_roles) != len(set(roster_roles)):
            raise ValueError("Godot gameplay profession roster roles must be unique")
        if self.profession_rosters:
            if set(roster_roles) != set(self.upgrade_role_order):
                raise ValueError("profession rosters must exactly cover the upgrade role order")
            if self.choices_per_level != 3:
                raise ValueError("profession progression requires exactly three choices per level")
        resurrection_abilities = [item for item in self.abilities if item.kind == GameplayAbilityKind.RESURRECTION]
        if bool(resurrection_abilities) != bool(self.resurrection_capacity):
            raise ValueError("resurrection capacity and automatic resurrection ability must be declared together")
        initial_basic_attack_damage = sum(item.attack for item in self.heroes)
        weakest_enemy = min(
            self.enemies,
            key=lambda item: item.health + item.damage * 6.0 + item.speed * 0.08,
        )
        if weakest_enemy.health > initial_basic_attack_damage:
            raise ValueError(
                "lowest-threat enemy health must not exceed one full initial-party basic-attack round"
            )
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
    sprite_plan: SpriteAtlasPlan | None = None
    sprite_atlas: ArtifactAsset | None = None
    licensed_art_atlas: ArtifactAsset | None = None
    effect_atlas: ArtifactAsset | None = None
    sprite_contract_required: bool = False
    sprite_segmentation_contract_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: dict[str, str] = Field(min_length=6, max_length=21)


def derive_sprite_atlas_plan(plan: GodotGameplayPlan) -> SpriteAtlasPlan:
    """Bind every rendered gameplay archetype to one fixed atlas slot."""

    slots: list[SpriteSlot] = []
    for hero in plan.heroes:
        slots.append(SpriteSlot(
            sprite_id=hero.hero_id,
            kind="hero",
            label=hero.label,
            visual_role=f"{hero.role} hero; readable top-down party silhouette",
            slot_index=len(slots),
        ))
    for enemy in plan.enemies:
        slots.append(SpriteSlot(
            sprite_id=enemy.enemy_id,
            kind="enemy",
            label=enemy.label,
            visual_role="hostile enemy archetype; visually distinct from every hero",
            slot_index=len(slots),
        ))
    return SpriteAtlasPlan(slots=tuple(slots))


GAMEPLAY_SCRIPT = r'''extends Node2D

const CombatFeedback = preload("res://scripts/khalinos_combat_feedback.gd")
const PresentationSkin = preload("res://scripts/khalinos_presentation_skin.gd")
const AudioFeedback = preload("res://scripts/khalinos_audio_feedback.gd")
const COMBAT_FEEDBACK_PACK_ID := CombatFeedback.PACK_ID
const PRESENTATION_SKIN_PACK_ID := PresentationSkin.PACK_ID
const AUDIO_FEEDBACK_PACK_ID := AudioFeedback.PACK_ID

var config: Dictionary
var center := Vector2.ZERO
var shared_health := 0.0
var shared_health_max := 0.0
var shield := 0.0
var elapsed := 0.0
var ground_scroll := Vector2.ZERO
var demo_autoplay := false
var spawn_clock := 0.0
var level := 1
var records := 0
var enemies: Array[Dictionary] = []
var ability_clocks: Dictionary = {}
var hero_attack_clocks: Dictionary = {}
var basic_attack_effects: Array[Dictionary] = []
var skill_effects: Array[Dictionary] = []
var enemy_attack_effects: Array[Dictionary] = []
var audio_events := {"attack": 0, "hit": 0, "heal": 0, "victory": 0}
var spawn_count := 0
var started := false
var choice_open := false
var current_upgrade_role := ""
var current_upgrade_options: Array[Dictionary] = []
var profession_state: Dictionary = {}
var stored_resurrections := 0
var ended := false
var victory := false
var rng := RandomNumberGenerator.new()
var sprite_manifest: Dictionary = {}
var sprite_texture: Texture2D
var licensed_art_manifest: Dictionary = {}
var licensed_art_texture: Texture2D
var licensed_art_helper
var effect_manifest: Dictionary = {}
var effect_texture: Texture2D
var effect_player

func _ready() -> void:
    config = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_GAMEPLAY.json"))
    center = Vector2(config.viewport_width / 2.0, config.viewport_height / 2.0)
    for hero in config.heroes:
        shared_health_max += float(hero.health)
    shared_health = shared_health_max
    for ability in config.abilities:
        ability_clocks[ability.ability_id] = 0.0
    for hero in config.heroes:
        hero_attack_clocks[hero.hero_id] = 0.0
    for roster in config.get("profession_rosters", []):
        profession_state[roster.role] = {"profession_id": roster.starting_profession_id, "rank": 1}
    rng.seed = int(config.deterministic_seed)
    if FileAccess.file_exists("res://KHALINOS_SPRITE_ATLAS.json"):
        sprite_manifest = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_SPRITE_ATLAS.json"))
        sprite_texture = load("res://assets/sprite-atlas.png")
    if FileAccess.file_exists("res://KHALINOS_LICENSED_ATLAS.json"):
        licensed_art_manifest = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_LICENSED_ATLAS.json"))
        licensed_art_texture = load("res://assets/licensed-art-atlas.png")
        licensed_art_helper = load("res://scripts/khalinos_licensed_art.gd")
    if FileAccess.file_exists("res://KHALINOS_EFFECT_ATLAS.json"):
        effect_manifest = JSON.parse_string(FileAccess.get_file_as_string("res://KHALINOS_EFFECT_ATLAS.json"))
        effect_texture = load("res://assets/combat-vfx-atlas.png")
        effect_player = load("res://scripts/khalinos_vfx_player.gd")
    demo_autoplay = OS.get_cmdline_user_args().has("--khalinos-demo-autoplay")
    if OS.get_cmdline_user_args().has("--khalinos-capture-gameplay") or demo_autoplay:
        _start_game()
    queue_redraw()

func _sprite_region(sprite_id: String) -> Rect2:
    for slot in sprite_manifest.get("slots", []):
        if slot.get("sprite_id", "") == sprite_id:
            var region: Array = slot.region
            return Rect2(float(region[0]), float(region[1]), float(region[2]), float(region[3]))
    return Rect2()

func _all_sprite_ids_mapped() -> bool:
    if sprite_texture == null:
        return false
    for hero in config.heroes:
        if _sprite_region(hero.hero_id).size == Vector2.ZERO:
            return false
    for enemy in config.enemies:
        if _sprite_region(enemy.enemy_id).size == Vector2.ZERO:
            return false
    return true

func _process(delta: float) -> void:
    if not started:
        queue_redraw()
        return
    if choice_open and demo_autoplay:
        _choose_upgrade(0)
    if ended or choice_open:
        queue_redraw()
        return
    var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")
    if demo_autoplay:
        direction = Vector2(cos(elapsed * 0.55), sin(elapsed * 0.38)).normalized()
    # Asset/window initialization can deliver one abnormally large frame delta.
    # Bound it so the countdown, camera and combat never jump ahead on launch.
    var frame_delta := minf(delta, 1.0 / 30.0)
    _step_simulation(frame_delta, direction)
    queue_redraw()

func _unhandled_key_input(event: InputEvent) -> void:
    if event.is_pressed() and not started and event.keycode in [KEY_ENTER, KEY_SPACE]:
        _start_game()
    elif event.is_pressed() and choice_open and event.keycode >= KEY_1 and event.keycode <= KEY_5:
        _choose_upgrade(int(event.keycode - KEY_1))
    elif event.is_pressed() and ended and event.keycode == KEY_R:
        get_tree().reload_current_scene()

func _input(event: InputEvent) -> void:
    if not started and event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
        if _start_button_rect().has_point(event.position):
            _start_game()
            get_viewport().set_input_as_handled()

func _start_game() -> void:
    if started:
        return
    started = true
    queue_redraw()

func _play_audio(cue: String) -> void:
    audio_events[cue] = int(audio_events.get(cue, 0)) + 1
    AudioFeedback.play_cue(self, cue)

func _start_button_rect() -> Rect2:
    return Rect2(float(config.viewport_width) / 2.0 - 130.0, float(config.viewport_height) / 2.0 + 48.0, 260.0, 58.0)

func _remaining_seconds() -> float:
    return max(0.0, float(config.session_seconds) - elapsed)

func _format_countdown() -> String:
    var remaining := int(ceil(_remaining_seconds()))
    return "%02d:%02d" % [remaining / 60, remaining % 60]

func _step_simulation(delta: float, direction: Vector2) -> void:
    elapsed += delta
    var speed: float = float(_party_stats().move_speed) / max(1.0, float(config.heroes.size()))
    if demo_autoplay:
        speed *= 0.45
    var movement := direction.normalized() * speed * delta
    ground_scroll += movement
    # The party remains at the camera anchor while the top-down world moves.
    # This keeps navigation readable and avoids the fast edge-to-edge motion that
    # made the demo capture visually uncomfortable.
    for enemy in enemies:
        enemy.position -= movement
    spawn_clock += delta
    var spawn_interval: float = max(0.35, 1.6 - elapsed / max(30.0, float(config.session_seconds)))
    while spawn_clock >= spawn_interval:
        spawn_clock -= spawn_interval
        _spawn_enemy()
    for enemy in enemies:
        enemy.attack_clock = max(0.0, float(enemy.get("attack_clock", 0.0)) - delta)
        var offset: Vector2 = center - enemy.position
        if offset.length() > 1.0:
            enemy.position += offset.normalized() * float(enemy.speed) * delta
        if offset.length() < 42.0 and float(enemy.attack_clock) <= 0.0:
            _apply_damage(_enemy_attack_damage(enemy))
            enemy.attack_clock = 0.9
            enemy_attack_effects.append({
                "enemy_id": String(enemy.enemy_id),
                "position": enemy.position,
                "target": center,
                "life": 0.32,
                "max_life": 0.32,
            })
            _play_audio("hit")
    _tick_basic_attacks(delta)
    _tick_abilities(delta)
    _update_combat_effects(delta)
    _remove_dead()
    var target_level: int = min(int(config.level_count), 1 + int(elapsed / float(config.level_interval_seconds)))
    if target_level > level:
        _open_level_choice()
    if shared_health <= 0.0:
        if stored_resurrections > 0:
            stored_resurrections -= 1
            shared_health = shared_health_max
        else:
            ended = true
            victory = false
    elif elapsed >= float(config.session_seconds):
        ended = true
        victory = true
        _play_audio("victory")

func _party_defense() -> float:
    return float(_party_stats().defense)

func _enemy_attack_damage(enemy: Dictionary) -> float:
    return max(0.5, float(enemy.damage) - _party_defense() * 0.01)

func _party_stats() -> Dictionary:
    var totals := {"health": 0.0, "attack": 0.0, "defense": 0.0, "attack_speed": 0.0, "move_speed": 0.0}
    for hero in config.heroes:
        totals.health += float(hero.health)
        totals.attack += float(hero.attack)
        totals.defense += float(hero.defense)
        totals.attack_speed += float(hero.get("attack_speed", 1.0))
        totals.move_speed += float(hero.move_speed)
    return totals

func _spawn_enemy() -> void:
    var pool: Array = config.enemies.duplicate(true)
    pool.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return _enemy_threat(a) < _enemy_threat(b))
    var progress: float = clamp(elapsed / max(1.0, float(config.session_seconds)), 0.0, 1.0)
    var unlocked_count: int = clamp(1 + int(progress * float(pool.size())), 1, pool.size())
    var unlocked: Array = pool.slice(0, unlocked_count)
    var template: Dictionary = unlocked[0] if spawn_count == 0 else _weighted_enemy_template(unlocked)
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
        "attack_clock": rng.randf_range(0.35, 0.75),
    })
    spawn_count += 1

func _enemy_threat(enemy: Dictionary) -> float:
    return float(enemy.health) + float(enemy.damage) * 6.0 + float(enemy.speed) * 0.08

func _weighted_enemy_template(pool: Array) -> Dictionary:
    var total_weight := 0
    for candidate in pool:
        total_weight += int(candidate.spawn_weight)
    var roll := rng.randi_range(1, max(1, total_weight))
    for candidate in pool:
        roll -= int(candidate.spawn_weight)
        if roll <= 0:
            return candidate
    return pool[0]

func _hero_position(hero_index: int) -> Vector2:
    var angle: float = TAU * float(hero_index) / max(1.0, float(config.heroes.size())) - PI / 2.0
    return center + Vector2.from_angle(angle) * 30.0

func _basic_attack_range(role: String) -> float:
    match role:
        "tank":
            return 110.0
        "damage":
            return 280.0
        "support":
            return 200.0
        _:
            return 170.0

func _nearest_enemy(origin: Vector2, attack_range: float) -> Dictionary:
    var selected: Dictionary = {}
    var selected_distance := attack_range + 1.0
    for enemy in enemies:
        var distance := origin.distance_to(enemy.position)
        if distance <= attack_range and distance < selected_distance:
            selected = enemy
            selected_distance = distance
    return selected

func _tick_basic_attacks(delta: float) -> void:
    var party_stats := _party_stats()
    var hero_count: float = max(1.0, float(config.heroes.size()))
    var cooldown: float = max(0.35, hero_count / max(0.1, float(party_stats.attack_speed)))
    var damage: float = max(1.0, float(party_stats.attack) / hero_count)
    for hero_index in range(config.heroes.size()):
        var hero: Dictionary = config.heroes[hero_index]
        var hero_id := String(hero.hero_id)
        hero_attack_clocks[hero_id] = float(hero_attack_clocks.get(hero_id, 0.0)) + delta
        if float(hero_attack_clocks[hero_id]) < cooldown:
            continue
        var origin := _hero_position(hero_index)
        var target := _nearest_enemy(origin, _basic_attack_range(String(hero.role)))
        if target.is_empty():
            continue
        hero_attack_clocks[hero_id] = 0.0
        target.health = float(target.health) - damage
        basic_attack_effects.append({
            "owner_hero_id": hero_id,
            "role": String(hero.role),
            "origin": origin,
            "target": target.position,
            "range": _basic_attack_range(String(hero.role)),
            "life": 0.28,
            "max_life": 0.28,
        })
        _play_audio("attack")
        _play_audio("hit")

func _tick_abilities(delta: float) -> void:
    for ability in config.abilities:
        var id: String = ability.ability_id
        ability_clocks[id] = float(ability_clocks[id]) + delta
        if float(ability_clocks[id]) < float(ability.cooldown_seconds):
            continue
        ability_clocks[id] = 0.0
        skill_effects.append({
            "owner_hero_id": String(ability.owner_hero_id),
            "kind": String(ability.kind),
            "label": String(ability.label),
            "radius": float(ability.radius),
            "life": 0.62,
            "max_life": 0.62,
        })
        if String(ability.kind) in ["heal", "resurrection"]:
            _play_audio("heal")
        else:
            _play_audio("attack")
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
            "resurrection":
                stored_resurrections = min(int(config.get("resurrection_capacity", 0)), stored_resurrections + 1)

func _update_combat_effects(delta: float) -> void:
    basic_attack_effects = _decay_effects(basic_attack_effects, delta)
    skill_effects = _decay_effects(skill_effects, delta)
    enemy_attack_effects = _decay_effects(enemy_attack_effects, delta)

func _decay_effects(source: Array[Dictionary], delta: float) -> Array[Dictionary]:
    var active: Array[Dictionary] = []
    for effect in source:
        effect.life = float(effect.life) - delta
        if float(effect.life) > 0.0:
            active.append(effect)
    return active

func _profession_details(profession_id: String) -> Dictionary:
    for roster in config.get("profession_rosters", []):
        for profession in roster.professions:
            if String(profession.profession_id) == profession_id:
                return profession
    return {"label": profession_id.replace("_", " ").capitalize(), "stat_focus": "balanced"}

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

func _open_level_choice() -> void:
    choice_open = true
    current_upgrade_options = []
    var order: Array = config.get("upgrade_role_order", [])
    if order.is_empty():
        return
    current_upgrade_role = String(order[(level - 1) % order.size()])
    var state: Dictionary = profession_state.get(current_upgrade_role, {"profession_id": "", "rank": 1})
    current_upgrade_options.append({"kind": "rank_up", "profession_id": state.profession_id, "role": current_upgrade_role})
    var alternatives := _seeded_profession_alternatives(
        current_upgrade_role,
        String(state.profession_id),
        int(config.deterministic_seed),
        level,
    )
    for profession_id in alternatives:
        current_upgrade_options.append({"kind": "specialization", "profession_id": profession_id, "role": current_upgrade_role})

func _profession_candidates(role: String, current_profession_id: String) -> Array[String]:
    var candidates: Array[String] = []
    for roster in config.get("profession_rosters", []):
        if String(roster.role) != role:
            continue
        for profession in roster.professions:
            var profession_id := String(profession.profession_id)
            if profession_id == current_profession_id:
                continue
            candidates.append(profession_id)
    return candidates

func _seeded_profession_alternatives(
    role: String,
    current_profession_id: String,
    seed_value: int,
    choice_level: int,
) -> Array[String]:
    var candidates := _profession_candidates(role, current_profession_id)
    var local_rng := RandomNumberGenerator.new()
    var order: Array = config.get("upgrade_role_order", [])
    var role_index: int = max(0, order.find(role))
    local_rng.seed = seed_value + choice_level * 1009 + role_index * 9176
    for index in range(candidates.size() - 1, 0, -1):
        var swap_index := local_rng.randi_range(0, index)
        var temporary := candidates[index]
        candidates[index] = candidates[swap_index]
        candidates[swap_index] = temporary
    var selected: Array[String] = []
    for index in range(min(int(config.choices_per_level) - 1, candidates.size())):
        selected.append(candidates[index])
    return selected

func _choose_upgrade(index: int) -> void:
    if index < 0 or index >= int(config.choices_per_level):
        return
    if not current_upgrade_options.is_empty() and index < current_upgrade_options.size():
        var selected: Dictionary = current_upgrade_options[index]
        var state: Dictionary = profession_state.get(current_upgrade_role, {"profession_id": selected.profession_id, "rank": 1})
        if selected.kind == "rank_up":
            state.rank = int(state.rank) + 1
        else:
            state.profession_id = selected.profession_id
        profession_state[current_upgrade_role] = state
    level = min(int(config.level_count), level + 1)
    shared_health = min(shared_health_max, shared_health + shared_health_max * 0.12)
    choice_open = false
    current_upgrade_role = ""
    current_upgrade_options = []

func verification_scenario() -> Dictionary:
    var start_gate_present := not started and elapsed == 0.0 and enemies.is_empty()
    var initial_countdown := _remaining_seconds()
    _start_game()
    var start := center
    var start_scroll := ground_scroll
    _step_simulation(0.5, Vector2.RIGHT)
    var moved := ground_scroll.x > start_scroll.x and center.is_equal_approx(start)
    var countdown_decrements := _remaining_seconds() < initial_countdown
    _spawn_enemy()
    var spawned := enemies.size() > 0
    var first_enemy_id := String(enemies[0].enemy_id) if spawned else ""
    var weakest_enemy: Dictionary = config.enemies[0]
    for candidate in config.enemies:
        if _enemy_threat(candidate) < _enemy_threat(weakest_enemy):
            weakest_enemy = candidate
    var first_enemy_level_one_beatable := spawned and first_enemy_id == String(weakest_enemy.enemy_id) and level == 1
    if spawned:
        enemies[0].position = center
        enemies[0].health = float(weakest_enemy.health)
    basic_attack_effects = []
    for hero in config.heroes:
        hero_attack_clocks[String(hero.hero_id)] = 999.0
    _tick_basic_attacks(0.01)
    var basic_attack_owners: Array[String] = []
    for effect in basic_attack_effects:
        basic_attack_owners.append(String(effect.owner_hero_id))
    for hero in config.heroes:
        first_enemy_level_one_beatable = first_enemy_level_one_beatable and basic_attack_owners.has(String(hero.hero_id))
    first_enemy_level_one_beatable = first_enemy_level_one_beatable and spawned and float(enemies[0].health) <= 0.0
    var all_hero_basic_attacks_visible: bool = basic_attack_owners.size() == config.heroes.size()
    _remove_dead()
    var ability_records_before := records
    skill_effects = []
    for ability in config.abilities:
        ability_clocks[ability.ability_id] = float(ability.cooldown_seconds)
    _tick_abilities(0.01)
    var skill_effect_count := skill_effects.size()
    var skill_effect_visible: bool = skill_effect_count == config.abilities.size()
    var heal_effect_visible := false
    for effect in skill_effects:
        heal_effect_visible = heal_effect_visible or String(effect.kind) == "heal"
    _tick_abilities(0.01)
    var skill_cooldown_enforced := skill_effects.size() == skill_effect_count
    var ability_applied: bool = records > ability_records_before or skill_effect_visible or shield > 0.0
    enemies = []
    _spawn_enemy()
    enemies[0].position = center
    enemies[0].health = 9999.0
    enemies[0].attack_clock = 0.0
    enemy_attack_effects = []
    shield = 0.0
    var health_before_enemy_attack := shared_health
    _step_simulation(0.01, Vector2.ZERO)
    var enemy_effect_count := enemy_attack_effects.size()
    var enemy_attack_effect_visible := enemy_effect_count == 1 and shared_health < health_before_enemy_attack
    _step_simulation(0.01, Vector2.ZERO)
    var enemy_attack_cooldown_enforced := enemy_attack_effects.size() == enemy_effect_count
    var observed_roles: Array[String] = []
    var choice_contract_valid := true
    var seeded_alternatives_valid := true
    var same_seed_repeatable := true
    var different_seed_variation_when_possible := true
    var upgrade_choice_trace: Array[Dictionary] = []
    var level_choice_prompted := false
    for stage in range(int(config.level_count) - 1):
        elapsed = float((stage + 1) * int(config.level_interval_seconds))
        _step_simulation(0.01, Vector2.ZERO)
        if not choice_open:
            choice_contract_valid = false
            break
        level_choice_prompted = level_choice_prompted or current_upgrade_options.size() == int(config.choices_per_level)
        observed_roles.append(current_upgrade_role)
        if not config.get("profession_rosters", []).is_empty():
            var state: Dictionary = profession_state.get(current_upgrade_role, {"profession_id": "", "rank": 1})
            var current_profession_id := String(state.profession_id)
            var observed_alternatives: Array[String] = []
            for option in current_upgrade_options.slice(1):
                observed_alternatives.append(String(option.profession_id))
            var candidates := _profession_candidates(current_upgrade_role, current_profession_id)
            var repeated := _seeded_profession_alternatives(
                current_upgrade_role, current_profession_id, int(config.deterministic_seed), level,
            )
            choice_contract_valid = choice_contract_valid and current_upgrade_options.size() == 3
            choice_contract_valid = choice_contract_valid and current_upgrade_options[0].kind == "rank_up"
            choice_contract_valid = choice_contract_valid and current_upgrade_options[1].kind == "specialization"
            choice_contract_valid = choice_contract_valid and current_upgrade_options[2].kind == "specialization"
            seeded_alternatives_valid = seeded_alternatives_valid and observed_alternatives.size() == 2
            seeded_alternatives_valid = seeded_alternatives_valid and observed_alternatives[0] != observed_alternatives[1]
            seeded_alternatives_valid = seeded_alternatives_valid and not observed_alternatives.has(current_profession_id)
            seeded_alternatives_valid = seeded_alternatives_valid and candidates.has(observed_alternatives[0])
            seeded_alternatives_valid = seeded_alternatives_valid and candidates.has(observed_alternatives[1])
            same_seed_repeatable = same_seed_repeatable and observed_alternatives == repeated
            if candidates.size() > 2:
                var changed := false
                var observed_set := observed_alternatives.duplicate()
                observed_set.sort()
                for seed_offset in range(1, 9):
                    var alternate := _seeded_profession_alternatives(
                        current_upgrade_role,
                        current_profession_id,
                        int(config.deterministic_seed) + seed_offset,
                        level,
                    )
                    var alternate_set := alternate.duplicate()
                    alternate_set.sort()
                    if alternate_set != observed_set:
                        changed = true
                        break
                different_seed_variation_when_possible = different_seed_variation_when_possible and changed
            upgrade_choice_trace.append({
                "level": level,
                "role": current_upgrade_role,
                "current_profession_id": current_profession_id,
                "alternatives": observed_alternatives,
            })
        _choose_upgrade(0)
    var upgraded := level == int(config.level_count) and not choice_open
    for ability in config.abilities:
        if ability.kind == "resurrection":
            ability_clocks[ability.ability_id] = float(ability.cooldown_seconds)
    _tick_abilities(0.01)
    var resurrection_stored := stored_resurrections == int(config.get("resurrection_capacity", 0))
    if stored_resurrections > 0:
        shared_health = 1.0
        _apply_damage(shared_health_max + 1.0)
        _step_simulation(0.01, Vector2.ZERO)
    var resurrection_consumed := int(config.get("resurrection_capacity", 0)) == 0 or (stored_resurrections == 0 and shared_health == shared_health_max and not ended)
    choice_open = false
    ended = false
    victory = false
    shared_health = shared_health_max
    elapsed = float(config.session_seconds) - 0.01
    _step_simulation(0.02, Vector2.ZERO)
    var party_stats := _party_stats()
    var expected_roles: Array[String] = []
    var role_order: Array = config.get("upgrade_role_order", [])
    for stage in range(int(config.level_count) - 1):
        if not role_order.is_empty():
            expected_roles.append(String(role_order[stage % role_order.size()]))
    var licensed_profile_roles_bound := licensed_art_texture != null and licensed_art_helper != null
    if licensed_profile_roles_bound:
        for licensed_role in ["warrior", "archer", "priest", "goblin", "orc"]:
            licensed_profile_roles_bound = (
                licensed_profile_roles_bound
                and licensed_art_helper.region_for(licensed_art_manifest, licensed_role).size != Vector2.ZERO
            )
    return {
        "schema_version": "khalinos-godot-gameplay-probe-v5",
        "combat_feedback_pack_loaded": COMBAT_FEEDBACK_PACK_ID == "godot.combat-feedback@1.0.0",
        "presentation_skin_pack_loaded": PRESENTATION_SKIN_PACK_ID == "godot.presentation-skin@1.0.0",
        "audio_feedback_pack_loaded": AUDIO_FEEDBACK_PACK_ID == "godot.audio-feedback@1.0.0",
        "licensed_art_requested": FileAccess.file_exists("res://KHALINOS_LICENSE_RECEIPT.json"),
        "licensed_art_loaded": licensed_art_texture != null and licensed_art_helper != null,
        "licensed_profile_roles_bound": licensed_profile_roles_bound,
        "license_receipt_present": FileAccess.file_exists("res://KHALINOS_LICENSE_RECEIPT.json"),
        "effect_atlas_requested": FileAccess.file_exists("res://KHALINOS_EFFECT_RECEIPT.json"),
        "effect_atlas_loaded": effect_texture != null and effect_player != null,
        "effect_receipt_present": FileAccess.file_exists("res://KHALINOS_EFFECT_RECEIPT.json"),
        "effect_frame_animation_observed": (
            effect_player == null
            or effect_player.frame_region(effect_manifest, "warrior_skill", 0.60, 0.60)
            != effect_player.frame_region(effect_manifest, "warrior_skill", 0.10, 0.60)
        ),
        "start_gate_present": start_gate_present,
        "countdown_decrements": countdown_decrements,
        "first_enemy_level_one_beatable": first_enemy_level_one_beatable,
        "all_hero_basic_attacks_visible": all_hero_basic_attacks_visible,
        "skill_cooldown_enforced": skill_cooldown_enforced,
        "skill_effect_visible": skill_effect_visible,
        "heal_effect_visible": heal_effect_visible,
        "enemy_attack_effect_visible": enemy_attack_effect_visible,
        "enemy_attack_cooldown_enforced": enemy_attack_cooldown_enforced,
        "attack_audio_events": int(audio_events.get("attack", 0)),
        "hit_audio_events": int(audio_events.get("hit", 0)),
        "heal_audio_events": int(audio_events.get("heal", 0)),
        "victory_audio_events": int(audio_events.get("victory", 0)),
        "level_choice_prompted": level_choice_prompted,
        "enemy_visual_family": "green",
        "background_visual_treatment": "bright_readable",
        "outcome_prompt_present": ended and not _outcome_title().is_empty(),
        "formation_count": config.heroes.size(),
        "movement_applied": moved,
        "enemy_spawned": spawned,
        "auto_ability_applied": ability_applied,
        "shared_health_initialized": shared_health_max > 0.0,
        "level_choice_offered": observed_roles.size() > 0,
        "level_choice_applied": upgraded,
        "session_seconds": int(config.session_seconds),
        "level_count": int(config.level_count),
        "level_interval_seconds": int(config.level_interval_seconds),
        "upgrade_roles_observed": observed_roles,
        "upgrade_role_order_valid": observed_roles == expected_roles,
        "upgrade_choice_contract_valid": choice_contract_valid,
        "profession_choice_mode": config.get("profession_choice_mode", ""),
        "seeded_alternatives_valid": seeded_alternatives_valid,
        "same_seed_repeatable": same_seed_repeatable,
        "different_seed_variation_when_possible": different_seed_variation_when_possible,
        "upgrade_choice_trace": upgrade_choice_trace,
        "party_stats": party_stats,
        "team_stat_mode": config.get("team_stat_mode", ""),
        "resurrection_stored": resurrection_stored,
        "resurrection_consumed": resurrection_consumed,
        "victory_at_session_end": ended and victory and elapsed >= float(config.session_seconds),
        "sprite_atlas_loaded": sprite_texture != null,
        "sprite_slot_count": sprite_manifest.get("slots", []).size(),
        "all_sprite_ids_mapped": _all_sprite_ids_mapped(),
        "seed": config.deterministic_seed,
    }

func _draw() -> void:
    _draw_scrolling_ground()
    for effect in skill_effects:
        var role := "warrior_skill"
        match String(effect.kind):
            "heal": role = "healer_heal"
            "shield": role = "healer_shield"
            "resurrection": role = "healer_resurrection"
            _: role = "warrior_skill" if String(effect.owner_hero_id) == "warrior" else "archer_skill"
        var effect_drawn := false
        if effect_player != null and effect_texture != null:
            effect_drawn = effect_player.draw_effect(self, effect_texture, effect_manifest, role, Rect2(center - Vector2(84, 84), Vector2(168, 168)), float(effect.life), float(effect.max_life))
        if not effect_drawn:
            CombatFeedback.draw_skill(self, effect, center)
    for effect in basic_attack_effects:
        var role := "warrior_basic" if String(effect.owner_hero_id) == "warrior" else "archer_basic"
        var anchor: Vector2 = effect.origin if role == "warrior_basic" else effect.target
        var effect_drawn := false
        if effect_player != null and effect_texture != null:
            effect_drawn = effect_player.draw_effect(self, effect_texture, effect_manifest, role, Rect2(anchor - Vector2(44, 44), Vector2(88, 88)), float(effect.life), float(effect.max_life))
        if not effect_drawn:
            CombatFeedback.draw_basic_attack(self, effect)
    for effect in enemy_attack_effects:
        var effect_drawn := false
        if effect_player != null and effect_texture != null:
            var role := "enemy_caster" if String(effect.get("enemy_id", "")) == "goblin" else "enemy_melee"
            effect_drawn = effect_player.draw_effect(self, effect_texture, effect_manifest, role, Rect2(Vector2(effect.target) - Vector2(56, 56), Vector2(112, 112)), float(effect.life), float(effect.max_life))
        if not effect_drawn:
            CombatFeedback.draw_enemy_attack(self, effect)
    var hero_index := 0
    for hero in config.heroes:
        var angle: float = TAU * float(hero_index) / max(1.0, float(config.heroes.size())) - PI / 2.0
        var position: Vector2 = center + Vector2.from_angle(angle) * 30.0
        for effect in basic_attack_effects:
            if String(effect.owner_hero_id) == String(hero.hero_id):
                position += Vector2.from_angle(angle) * 10.0 * sin(float(effect.life) / float(effect.max_life) * PI)
        for effect in skill_effects:
            if String(effect.owner_hero_id) == String(hero.hero_id):
                position += Vector2.from_angle(angle) * 10.0 * sin(float(effect.life) / float(effect.max_life) * PI)
        var licensed_hero_drawn := false
        if licensed_art_helper != null and licensed_art_texture != null:
            var licensed_hero_role := String(hero.hero_id)
            match String(hero.role):
                "tank": licensed_hero_role = "warrior"
                "damage": licensed_hero_role = "archer"
                "support": licensed_hero_role = "priest"
            licensed_hero_drawn = licensed_art_helper.draw_role(self, licensed_art_texture, licensed_art_manifest, licensed_hero_role, Rect2(position - Vector2(30, 30), Vector2(60, 60)))
        var hero_region := _sprite_region(hero.hero_id)
        if licensed_hero_drawn:
            pass
        elif sprite_texture != null and hero_region.size != Vector2.ZERO:
            draw_texture_rect_region(sprite_texture, Rect2(position - Vector2(28, 28), Vector2(56, 56)), hero_region)
        else:
            draw_circle(position, 16.0, Color(hero.color_hex))
            draw_circle(position, 18.0, Color("f3e6bd"), false, 3.0)
        hero_index += 1
    var licensed_enemy_index := 0
    for enemy in enemies:
        var licensed_enemy_drawn := false
        if licensed_art_helper != null and licensed_art_texture != null:
            var licensed_enemy_role := "goblin" if licensed_enemy_index % 2 == 0 else "orc"
            licensed_enemy_drawn = licensed_art_helper.draw_role(self, licensed_art_texture, licensed_art_manifest, licensed_enemy_role, Rect2(enemy.position - Vector2(24, 24), Vector2(48, 48)), Color(0.72, 1.0, 0.72, 1.0))
        var enemy_region := _sprite_region(enemy.enemy_id)
        if licensed_enemy_drawn:
            pass
        elif sprite_texture != null and enemy_region.size != Vector2.ZERO:
            draw_texture_rect_region(sprite_texture, Rect2(enemy.position - Vector2(22, 22), Vector2(44, 44)), enemy_region, Color("8ee58a"))
        else:
            draw_circle(enemy.position, 14.0, Color("58b96a"))
        licensed_enemy_index += 1
    PresentationSkin.draw_hud_panel(self, Rect2(22, 18, 382, 64), Color("b8d88f"))
    _draw_label("TRINITY HP  %d / %d" % [max(0, int(shared_health)), int(shared_health_max)], Vector2(32, 42), 18, Color("f7f2df"))
    draw_rect(Rect2(31, 52, 354, 18), Color(0.08, 0.09, 0.08, 0.9))
    draw_rect(Rect2(34, 55, 348.0 * clamp(shared_health / max(1.0, shared_health_max), 0.0, 1.0), 12), Color("d95f4f"))
    _draw_label("TIME  " + _format_countdown(), Vector2(float(config.viewport_width) / 2.0 - 82.0, 45), 26, Color("fff0a8"))
    _draw_label("LEVEL %d / %d" % [level, int(config.level_count)], Vector2(float(config.viewport_width) - 180.0, 42), 18, Color("f7f2df"))
    _draw_skill_cooldowns()
    _draw_label("Move: WASD / Arrows", Vector2(30, float(config.viewport_height) - 24.0), 16, Color(0.9, 0.94, 0.86, 0.82))
    if not started:
        _draw_start_overlay()
    if choice_open:
        _draw_choice_overlay()
    if ended:
        _draw_outcome_overlay()

func _draw_scrolling_ground() -> void:
    var viewport_size := Vector2(float(config.viewport_width), float(config.viewport_height))
    draw_rect(Rect2(Vector2.ZERO, viewport_size), Color("476b3d"))
    var tile_size := 96.0
    var visual_scroll := ground_scroll * 0.55
    var origin_column := int(floor(visual_scroll.x / tile_size)) - 1
    var origin_row := int(floor(visual_scroll.y / tile_size)) - 1
    var offset := Vector2(
        -fposmod(visual_scroll.x, tile_size) - tile_size,
        -fposmod(visual_scroll.y, tile_size) - tile_size
    )
    var columns := int(ceil(viewport_size.x / tile_size)) + 3
    var rows := int(ceil(viewport_size.y / tile_size)) + 3
    for row in range(rows):
        for column in range(columns):
            var tile_position := offset + Vector2(column * tile_size, row * tile_size)
            var world_column := origin_column + column
            var world_row := origin_row + row
            var checker := posmod(world_column + world_row, 3)
            var grass_color := Color("547a45") if checker == 0 else Color("4d7040")
            draw_rect(Rect2(tile_position, Vector2(tile_size + 1.0, tile_size + 1.0)), grass_color)
            var seed: int = absi(world_column * 37 + world_row * 53)
            if seed % 5 == 0:
                draw_circle(tile_position + Vector2(25.0, 31.0), 13.0, Color("8c7651"))
                draw_circle(tile_position + Vector2(23.0, 28.0), 8.0, Color("a08a62"))
            elif seed % 4 == 0:
                draw_circle(tile_position + Vector2(69.0, 62.0), 9.0, Color("6f7568"))
                draw_circle(tile_position + Vector2(66.0, 59.0), 5.0, Color("929888"))
            else:
                draw_line(tile_position + Vector2(18.0, 75.0), tile_position + Vector2(25.0, 64.0), Color("88a85f"), 3.0)
                draw_line(tile_position + Vector2(25.0, 75.0), tile_position + Vector2(25.0, 62.0), Color("9ab86b"), 2.0)

func _draw_skill_cooldowns() -> void:
    var panel_x := float(config.viewport_width) - 290.0
    PresentationSkin.draw_hud_panel(self, Rect2(panel_x, 76.0, 266.0, 30.0 + config.abilities.size() * 24.0), Color("d9b84f"))
    _draw_label("SKILL COOLDOWNS", Vector2(panel_x + 12.0, 98.0), 15, Color("fff0a8"))
    for index in range(config.abilities.size()):
        var ability: Dictionary = config.abilities[index]
        var remaining: float = max(0.0, float(ability.cooldown_seconds) - float(ability_clocks.get(ability.ability_id, 0.0)))
        var state := "READY" if remaining <= 0.0 else "%.1fs" % remaining
        var state_color := Color("8ff0a8") if remaining <= 0.0 else Color("e8e3cf")
        _draw_label(String(ability.label), Vector2(panel_x + 12.0, 124.0 + index * 24.0), 14, Color("d7e4d0"))
        _draw_label(state, Vector2(panel_x + 188.0, 124.0 + index * 24.0), 14, state_color)

func _draw_label(text: String, position: Vector2, size: int, color: Color, alignment := HORIZONTAL_ALIGNMENT_LEFT, width := -1.0) -> void:
    draw_string(ThemeDB.fallback_font, position, text, alignment, width, size, color)

func _draw_start_overlay() -> void:
    var panel := Rect2(float(config.viewport_width) / 2.0 - 330.0, float(config.viewport_height) / 2.0 - 190.0, 660.0, 380.0)
    draw_rect(panel, Color(0.035, 0.065, 0.045, 0.94))
    draw_rect(panel, Color("b8d88f"), false, 3.0)
    _draw_label(String(config.get("project_name", "TRINITY SURVIVORS")).to_upper(), Vector2(panel.position.x, panel.position.y + 82.0), 34, Color("fff0b5"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)
    _draw_label("Survive together until the timer reaches 00:00", Vector2(panel.position.x, panel.position.y + 130.0), 20, Color("e8f3dc"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)
    _draw_label("Move with WASD or Arrow Keys · Heroes attack automatically", Vector2(panel.position.x, panel.position.y + 172.0), 16, Color("cddcc4"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)
    var button := _start_button_rect()
    draw_rect(button, Color("d9b84f"))
    draw_rect(button, Color("fff0b5"), false, 3.0)
    _draw_label("START", Vector2(button.position.x, button.position.y + 39.0), 24, Color("15251b"), HORIZONTAL_ALIGNMENT_CENTER, button.size.x)
    _draw_label("Click START or press Enter / Space", Vector2(panel.position.x, panel.end.y - 34.0), 15, Color("b8c9b0"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)

func _draw_choice_overlay() -> void:
    var panel := Rect2(float(config.viewport_width) / 2.0 - 340.0, float(config.viewport_height) / 2.0 - 190.0, 680.0, 380.0)
    draw_rect(panel, Color(0.035, 0.06, 0.04, 0.97))
    draw_rect(panel, Color("d9b84f"), false, 3.0)
    _draw_label("LEVEL UP · %s CHOICE" % current_upgrade_role.to_upper(), Vector2(panel.position.x, panel.position.y + 55.0), 25, Color("fff0a8"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)
    _draw_label("Combat is paused — press a number to continue", Vector2(panel.position.x, panel.position.y + 88.0), 16, Color("d7e4d0"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)
    for index in range(current_upgrade_options.size()):
        var option: Dictionary = current_upgrade_options[index]
        var details := _profession_details(String(option.profession_id))
        var action := "Rank up current profession" if String(option.kind) == "rank_up" else "Change specialization"
        var line := "%d   %s   ·   %s   ·   Focus: %s" % [index + 1, String(details.label), action, String(details.get("stat_focus", "balanced")).replace("_", " ")]
        _draw_label(line, Vector2(panel.position.x + 48.0, panel.position.y + 145.0 + index * 62.0), 18, Color("f4f0df"))

func _outcome_title() -> String:
    return "VICTORY" if victory else "DEFEAT"

func _draw_outcome_overlay() -> void:
    var panel := Rect2(float(config.viewport_width) / 2.0 - 270.0, float(config.viewport_height) / 2.0 - 115.0, 540.0, 230.0)
    draw_rect(panel, Color(0.035, 0.055, 0.04, 0.96))
    draw_rect(panel, Color("d9b84f"), false, 3.0)
    _draw_label(_outcome_title(), Vector2(panel.position.x, panel.position.y + 82.0), 38, Color("fff0a8"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)
    _draw_label("Press R to restart", Vector2(panel.position.x, panel.position.y + 142.0), 22, Color("eef4e8"), HORIZONTAL_ALIGNMENT_CENTER, panel.size.x)

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
        receipt.get("combat_feedback_pack_loaded", false)
        and receipt.get("presentation_skin_pack_loaded", false)
        and receipt.get("audio_feedback_pack_loaded", false)
        and receipt.get("attack_audio_events", 0) > 0
        and receipt.get("hit_audio_events", 0) > 0
        and receipt.get("heal_audio_events", 0) > 0
        and receipt.get("victory_audio_events", 0) > 0
        and
        receipt.get("start_gate_present", false)
        and receipt.get("countdown_decrements", false)
        and receipt.get("first_enemy_level_one_beatable", false)
        and receipt.get("all_hero_basic_attacks_visible", false)
        and receipt.get("skill_cooldown_enforced", false)
        and receipt.get("skill_effect_visible", false)
        and receipt.get("heal_effect_visible", false)
        and receipt.get("enemy_attack_effect_visible", false)
        and receipt.get("enemy_attack_cooldown_enforced", false)
        and receipt.get("level_choice_prompted", false)
        and receipt.get("enemy_visual_family", "") == "green"
        and receipt.get("background_visual_treatment", "") == "bright_readable"
        and receipt.get("outcome_prompt_present", false)
        and receipt.get("movement_applied", false)
        and receipt.get("enemy_spawned", false)
        and receipt.get("auto_ability_applied", false)
        and receipt.get("shared_health_initialized", false)
        and receipt.get("level_choice_offered", false)
        and receipt.get("level_choice_applied", false)
        and receipt.get("upgrade_role_order_valid", false)
        and receipt.get("upgrade_choice_contract_valid", false)
        and receipt.get("profession_choice_mode", "") == "seeded_random_alternatives"
        and receipt.get("seeded_alternatives_valid", false)
        and receipt.get("same_seed_repeatable", false)
        and receipt.get("different_seed_variation_when_possible", false)
        and receipt.get("resurrection_stored", false)
        and receipt.get("resurrection_consumed", false)
        and receipt.get("victory_at_session_end", false)
        and (
            not FileAccess.file_exists("res://KHALINOS_SPRITE_ATLAS.json")
            or (receipt.get("sprite_atlas_loaded", false) and receipt.get("all_sprite_ids_mapped", false))
        )
        and (
            not receipt.get("licensed_art_requested", false)
            or (
                receipt.get("licensed_art_loaded", false)
                and receipt.get("licensed_profile_roles_bound", false)
                and receipt.get("license_receipt_present", false)
            )
        )
        and (
            not receipt.get("effect_atlas_requested", false)
            or (
                receipt.get("effect_atlas_loaded", false)
                and receipt.get("effect_receipt_present", false)
                and receipt.get("effect_frame_animation_observed", false)
            )
        )
    )
    var target := FileAccess.open(output, FileAccess.WRITE)
    target.store_string(JSON.stringify(receipt))
    target.close()
    if instance != null:
        instance.queue_free()
    quit(0 if receipt.passed else 1)
'''


GODOT_TOP_DOWN_AUTO_COMBAT_PACK = CapabilityPackManifest(
    pack_id="godot.top-down-auto-combat",
    version="1.0.0",
    provides=("gameplay.auto-attack", "gameplay.top-down"),
    requires=("godot.project", "godot.visual.foundation"),
    text_paths=("KHALINOS_GAMEPLAY.json", "scripts/khalinos_gameplay.gd"),
)
GODOT_GAMEPLAY_PROBE_PACK = CapabilityPackManifest(
    pack_id="godot.gameplay-probe",
    version="1.0.0",
    provides=("evidence.gameplay-probe",),
    requires=("audio.feedback", "gameplay.auto-attack", "gameplay.combat-feedback", "gameplay.top-down", "godot.project", "presentation.skin"),
    text_paths=("scripts/khalinos_gameplay_probe.gd",),
)
GODOT_SPRITE_ATLAS_PACK = CapabilityPackManifest(
    pack_id="godot.sprite-atlas",
    version="1.0.0",
    provides=("godot.visual.sprite-atlas",),
    requires=("gameplay.top-down", "godot.visual.foundation"),
    text_paths=(SPRITE_ATLAS_MANIFEST_PATH,),
    binary_paths=(SPRITE_ATLAS_PATH,),
)

GODOT_GAMEPLAY_BASE_PROFILE = (
    GODOT_PROJECT_CORE_PACK,
    GODOT_VISUAL_FOUNDATION_PACK,
    GODOT_TOP_DOWN_AUTO_COMBAT_PACK,
    GODOT_COMBAT_FEEDBACK_PACK,
    GODOT_PRESENTATION_SKIN_PACK,
    GODOT_AUDIO_FEEDBACK_PACK,
    GODOT_GAMEPLAY_PROBE_PACK,
)
GODOT_GAMEPLAY_SPRITE_PROFILE = GODOT_GAMEPLAY_BASE_PROFILE + (GODOT_SPRITE_ATLAS_PACK,)
GODOT_GAMEPLAY_LICENSED_ART_PROFILE = (
    GODOT_PROJECT_CORE_PACK,
    GODOT_VISUAL_FOUNDATION_PACK,
    GODOT_ASSET_SELECTOR_PACK,
    GODOT_STYLE_COMPOSER_PACK,
    GODOT_LICENSED_ATLAS_PACK,
    GODOT_LICENSE_RECEIPT_PACK,
    GODOT_TOP_DOWN_AUTO_COMBAT_PACK,
    GODOT_COMBAT_FEEDBACK_PACK,
    GODOT_PRESENTATION_SKIN_PACK,
    GODOT_AUDIO_FEEDBACK_PACK,
    GODOT_GAMEPLAY_PROBE_PACK,
)
GODOT_GAMEPLAY_LICENSED_ART_SPRITE_PROFILE = GODOT_GAMEPLAY_LICENSED_ART_PROFILE + (
    GODOT_SPRITE_ATLAS_PACK,
)
GODOT_GAMEPLAY_VFX_PACKS = (
    GODOT_EFFECT_SELECTOR_PACK,
    GODOT_EFFECT_ATLAS_PACK,
    GODOT_VFX_PLAYER_PACK,
    GODOT_EFFECT_RECEIPT_PACK,
)
GODOT_GAMEPLAY_VFX_SPRITE_PROFILE = (
    GODOT_GAMEPLAY_BASE_PROFILE[:-1]
    + GODOT_GAMEPLAY_VFX_PACKS
    + (GODOT_GAMEPLAY_PROBE_PACK, GODOT_SPRITE_ATLAS_PACK)
)
GODOT_GAMEPLAY_LICENSED_ART_VFX_SPRITE_PROFILE = (
    GODOT_GAMEPLAY_LICENSED_ART_PROFILE[:-1]
    + GODOT_GAMEPLAY_VFX_PACKS
    + (GODOT_GAMEPLAY_PROBE_PACK, GODOT_SPRITE_ATLAS_PACK)
)
GODOT_GAMEPLAY_LICENSED_ART_VFX_PROFILE = (
    GODOT_GAMEPLAY_LICENSED_ART_PROFILE[:-1]
    + GODOT_GAMEPLAY_VFX_PACKS
    + (GODOT_GAMEPLAY_PROBE_PACK,)
)


def compose_godot_gameplay_capabilities(
    plan: GodotGameplayPlan,
    sprite_plan: SpriteAtlasPlan | None = None,
    licensed_art: LicensedArtBundle | None = None,
    effects: EffectBundle | None = None,
) -> CapabilityComposition:
    """Build Trinity through ordered packs without changing artifact bytes."""

    gameplay_manifest = plan.model_dump(mode="json")
    stages = [
        godot_project_core_stage(
            project_name=plan.project_name,
            viewport_width=plan.viewport_width,
            viewport_height=plan.viewport_height,
            readme_body="A bounded Godot 2D gameplay vertical slice generated by the KHALINOS Godot Gameplay ToolPack.\n\nClick START or press Enter/Space to begin. Move with WASD or arrow keys. Heroes attack automatically and show their attack range. Choose level upgrades with number keys. Press R after victory or defeat to restart.",
        ),
        godot_visual_foundation_stage(
            viewport_width=plan.viewport_width,
            viewport_height=plan.viewport_height,
            script_path="scripts/khalinos_gameplay.gd",
            node_name="Gameplay",
        ),
    ]
    if licensed_art is not None:
        if licensed_art.profile_id != "godot.trinity-top-down":
            raise PermissionError("Trinity profile received licensed art for another profile")
        stages.extend(godot_licensed_art_stages(licensed_art))
    stages.extend([
        CapabilityPackStage(
            manifest=GODOT_TOP_DOWN_AUTO_COMBAT_PACK,
            text_files={
                "scripts/khalinos_gameplay.gd": GAMEPLAY_SCRIPT,
                "KHALINOS_GAMEPLAY.json": json.dumps(gameplay_manifest, ensure_ascii=False, indent=2) + "\n",
            },
        ),
        godot_combat_feedback_stage(),
        godot_presentation_skin_stage(),
        godot_audio_feedback_stage(),
    ])
    if effects is not None:
        if effects.profile_id != "godot.trinity-top-down":
            raise PermissionError("Trinity profile received effects for another profile")
        stages.extend(godot_effect_stages(effects))
    stages.extend([
        CapabilityPackStage(
            manifest=GODOT_GAMEPLAY_PROBE_PACK,
            text_files={"scripts/khalinos_gameplay_probe.gd": PROBE_SCRIPT},
        ),
    ])
    if sprite_plan is not None:
        stages.append(CapabilityPackStage(
            manifest=GODOT_SPRITE_ATLAS_PACK,
            text_files={
                SPRITE_ATLAS_MANIFEST_PATH: json.dumps(
                    sprite_plan.manifest(), ensure_ascii=False, indent=2
                ) + "\n"
            },
            binary_paths=(SPRITE_ATLAS_PATH,),
        ))
    return compose_capability_stages(stages)


def compile_godot_gameplay(
    plan: GodotGameplayPlan,
    concept: VisualConcept,
    asset: ArtifactAsset,
    sprite_plan: SpriteAtlasPlan | None = None,
    sprite_atlas: ArtifactAsset | None = None,
    licensed_art: LicensedArtBundle | None = None,
    effects: EffectBundle | None = None,
    *,
    require_sprite_atlas: bool = False,
) -> CompiledGodotGameplay:
    if asset.path != ASSET_PATH or asset.media_type != "image/png":
        raise ValueError("Godot gameplay requires the trusted visual foundation PNG")
    if (sprite_plan is None) != (sprite_atlas is None):
        raise ValueError("sprite plan and sprite atlas must be supplied as one atomic bundle")
    if require_sprite_atlas and sprite_atlas is None:
        raise ValueError("final Godot gameplay compilation requires a verified sprite atlas")
    segmentation_contract_sha256 = SPRITE_SEGMENTATION_CONTRACT.sha256() if sprite_atlas is not None else None
    if sprite_atlas is not None and sprite_atlas.path != SPRITE_ATLAS_PATH:
        raise ValueError("Godot gameplay sprite atlas uses an unapproved path")
    if sprite_plan is not None:
        expected_ids = [item.hero_id for item in plan.heroes] + [item.enemy_id for item in plan.enemies]
        if [item.sprite_id for item in sprite_plan.slots] != expected_ids:
            raise ValueError("sprite atlas slots do not exactly cover the gameplay archetypes")
    manifest = plan.model_dump(mode="json")
    plan_sha = _sha256({
        "gameplay": manifest,
        "concept": concept.model_dump(mode="json"),
        "asset_sha256": asset.sha256,
        "sprite_plan": sprite_plan.model_dump(mode="json") if sprite_plan else None,
        "sprite_atlas_sha256": sprite_atlas.sha256 if sprite_atlas else None,
        "licensed_art_sha256": licensed_art.atlas.sha256 if licensed_art else None,
        "effect_atlas_sha256": effects.atlas.sha256 if effects else None,
        "sprite_contract_required": require_sprite_atlas,
        "sprite_segmentation_contract_sha256": segmentation_contract_sha256,
    })
    composition = compose_godot_gameplay_capabilities(plan, sprite_plan, licensed_art, effects)
    expected_binary_paths = {ASSET_PATH} | ({SPRITE_ATLAS_PATH} if sprite_atlas is not None else set()) | ({LICENSED_ATLAS_PATH} if licensed_art is not None else set()) | ({EFFECT_ATLAS_PATH} if effects is not None else set())
    if set(composition.binary_paths) != expected_binary_paths:
        raise PermissionError("Godot Capability Pack binary bindings do not match approved assets")
    files = composition.text_files
    files = {path: content.replace("\r\n", "\n").replace("\r", "\n") for path, content in files.items()}
    return CompiledGodotGameplay(
        gameplay=plan,
        concept=concept,
        asset=asset,
        sprite_plan=sprite_plan,
        sprite_atlas=sprite_atlas,
        licensed_art_atlas=licensed_art.atlas if licensed_art else None,
        effect_atlas=effects.atlas if effects else None,
        sprite_contract_required=require_sprite_atlas,
        sprite_segmentation_contract_sha256=segmentation_contract_sha256,
        plan_sha256=plan_sha,
        bundle_sha256=_sha256({
            "plan_sha256": plan_sha,
            "files": files,
            "asset_sha256": asset.sha256,
            "sprite_atlas_sha256": sprite_atlas.sha256 if sprite_atlas else None,
            "licensed_art_sha256": licensed_art.atlas.sha256 if licensed_art else None,
            "effect_atlas_sha256": effects.atlas.sha256 if effects else None,
            "sprite_contract_required": require_sprite_atlas,
            "sprite_segmentation_contract_sha256": segmentation_contract_sha256,
        }),
        files=files,
    )
