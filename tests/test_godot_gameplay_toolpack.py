from __future__ import annotations

import hashlib
import struct
import zlib
import io

import pytest
from PIL import Image, ImageDraw

from khalinos.godot_gameplay import (
    CompiledGodotGameplay,
    GameplayAbility,
    GameplayEnemy,
    GameplayHero,
    GameplayProfession,
    GameplayProfessionRoster,
    GodotGameplayPlan,
    GodotGameplayProjectPlan,
    compile_godot_gameplay,
    derive_sprite_atlas_plan,
    explicit_gameplay_criteria,
    validate_gameplay_plan_requirements,
)
from khalinos.godot_gameplay_toolpack import GODOT_GAMEPLAY_MANIFEST, GODOT_GAMEPLAY_TOOLPACK
from khalinos.godot_gameplay_workflow import execute_godot_gameplay_run
from khalinos.models import (
    AgentVerification, CriterionFinding, DeterministicEvidence, QuestPlan, QuestSpec,
    RunRecord, RunStatus, SpriteAtlasGate, SpriteSlotVisualFinding, UserBrief, VisualAssessment, VisualAssetGate, VisualConcept,
    VisualConceptPlan, VisualSelection, canonical_sha256,
)
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.sprite_assets import SPRITE_SEGMENTATION_CONTRACT
from khalinos.storage import LocalRunStore
from khalinos.toolpacks import RegisteredToolPack, ToolPackRegistry


def test_gameplay_toolpack_binds_the_exact_sprite_segmentation_weight() -> None:
    dependencies = {
        item.dependency_id: item for item in GODOT_GAMEPLAY_MANIFEST.external_dependencies
    }
    dependency = dependencies["isnet-anime.onnx"]
    assert dependency.sha256 == SPRITE_SEGMENTATION_CONTRACT.model_sha256
    assert dependency.byte_size == SPRITE_SEGMENTATION_CONTRACT.model_bytes
    assert dependency.version == SPRITE_SEGMENTATION_CONTRACT.model_version
from khalinos.visual_assets import trusted_png_asset
from khalinos.sprite_assets import normalize_sprite_atlas


def png(width: int = 256, height: int = 256) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    rows = b"".join(
        b"\x00" + b"".join(bytes(((x * 3) % 256, (y * 2) % 256, (x + y) % 256, 255)) for x in range(width))
        for y in range(height)
    )
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def gameplay_plan() -> GodotGameplayPlan:
    return GodotGameplayPlan(
        project_name="Trinity Trial",
        session_seconds=60,
        heroes=(
            GameplayHero(hero_id="warrior", label="Warrior", role="tank", color_hex="D9A441", health=140, attack=18, defense=14, move_speed=180),
            GameplayHero(hero_id="archer", label="Archer", role="damage", color_hex="74B86A", health=90, attack=28, defense=5, move_speed=210),
            GameplayHero(hero_id="priest", label="Priest", role="support", color_hex="8AB4D8", health=100, attack=9, defense=8, move_speed=190),
        ),
        enemies=(
            GameplayEnemy(enemy_id="goblin", label="Goblin", color_hex="79A94B", health=20, damage=6, speed=70, record_value=4, spawn_weight=70),
            GameplayEnemy(enemy_id="orc", label="Orc", color_hex="A36E44", health=40, damage=10, speed=50, record_value=8, spawn_weight=30),
        ),
        abilities=(
            GameplayAbility(ability_id="sweep", label="Sweeping Arc", owner_hero_id="warrior", kind="damage", cooldown_seconds=1, power=25, radius=100),
            GameplayAbility(ability_id="volley", label="Arrow Volley", owner_hero_id="archer", kind="damage", cooldown_seconds=1.5, power=20, radius=180),
            GameplayAbility(ability_id="prayer", label="Restoring Prayer", owner_hero_id="priest", kind="heal", cooldown_seconds=3, power=16, radius=120),
            GameplayAbility(ability_id="revive", label="Stored Resurrection", owner_hero_id="priest", kind="resurrection", cooldown_seconds=5, power=1, radius=120),
        ),
        level_count=3,
        level_interval_seconds=20,
        choices_per_level=3,
        profession_rosters=(
            GameplayProfessionRoster(role="tank", starting_profession_id="warrior", professions=(
                GameplayProfession(profession_id="warrior", label="Warrior", role="tank", stat_focus="balanced"),
                GameplayProfession(profession_id="shield_warrior", label="Shield Warrior", role="tank", stat_focus="defense"),
                GameplayProfession(profession_id="axe_warrior", label="Axe Warrior", role="tank", stat_focus="attack"),
                GameplayProfession(profession_id="dual_swordsman", label="Dual Swordsman", role="tank", stat_focus="attack_speed"),
            )),
            GameplayProfessionRoster(role="damage", starting_profession_id="archer", professions=(
                GameplayProfession(profession_id="archer", label="Archer", role="damage", stat_focus="balanced"),
                GameplayProfession(profession_id="crossbowman", label="Crossbowman", role="damage", stat_focus="move_speed"),
                GameplayProfession(profession_id="longbowman", label="Longbowman", role="damage", stat_focus="attack"),
                GameplayProfession(profession_id="rifleman", label="Rifleman", role="damage", stat_focus="attack_speed"),
            )),
            GameplayProfessionRoster(role="support", starting_profession_id="priest", professions=(
                GameplayProfession(profession_id="priest", label="Priest", role="support", stat_focus="utility"),
                GameplayProfession(profession_id="paladin", label="Paladin", role="support", stat_focus="defense"),
                GameplayProfession(profession_id="dark_priest", label="Dark Priest", role="support", stat_focus="attack"),
                GameplayProfession(profession_id="guardian_priest", label="Guardian Priest", role="support", stat_focus="health"),
            )),
        ),
        resurrection_capacity=1,
        deterministic_seed=20260819,
    )


def sprite_asset(plan=None):
    plan = plan or derive_sprite_atlas_plan(gameplay_plan())
    image = Image.new("RGBA", (1024, 768), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    colors = ["#d9a441", "#74b86a", "#8ab4d8", "#79a94b", "#a36e44"]
    for slot, color in zip(plan.slots, colors, strict=True):
        left, top, width, height = slot.region()
        draw.ellipse((left + 72, top + 48, left + width - 72, top + height - 48), fill=color, outline="#2b271f", width=6)
        draw.rectangle((left + 104, top + 96, left + 152, top + 205), fill=color)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return normalize_sprite_atlas(output.getvalue(), plan)


def artifact() -> CompiledGodotGameplay:
    concept = VisualConcept(
        candidate_id="V1",
        name="Verdant Ruins",
        design_thesis="A readable ancient field keeps the formation and incoming threats visually distinct.",
        composition="The party anchors the center while enemies enter from a broad low-detail perimeter.",
        typography="Compact high-contrast status labels preserve gameplay visibility.",
        palette=["moss", "sandstone", "ember"],
        interaction_emphasis="Formation, health, and level choice remain the strongest signals.",
        anti_goals=["generic dashboard cards", "text baked into imagery"],
    )
    plan = gameplay_plan()
    sprite_plan = derive_sprite_atlas_plan(plan)
    return compile_godot_gameplay(
        plan, concept, trusted_png_asset(png()), sprite_plan, sprite_asset(sprite_plan),
        require_sprite_atlas=True,
    )


def test_registry_resolves_separate_gameplay_binding() -> None:
    binding = APPROVED_TOOLPACKS.binding_for("godot.gameplay")
    assert APPROVED_TOOLPACKS.resolve(binding) is GODOT_GAMEPLAY_TOOLPACK
    assert binding.version == "1.6.0"


def test_gameplay_compiler_is_deterministic_and_materializes_only_bounded_files(tmp_path) -> None:
    first = artifact()
    second = artifact()
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.gameplay.profession_choice_mode == "seeded_random_alternatives"
    assert "_seeded_profession_alternatives" in first.files["scripts/khalinos_gameplay.gd"]
    gameplay_script = first.files["scripts/khalinos_gameplay.gd"]
    assert "func _draw_start_overlay" in gameplay_script
    assert "func _format_countdown" in gameplay_script
    assert "basic_attack_effects.append" in gameplay_script
    assert "skill_effects.append" in gameplay_script
    assert "enemy_attack_effects.append" in gameplay_script
    assert "func _draw_skill_cooldowns" in gameplay_script
    assert 'Color("8ee58a")' in gameplay_script
    assert "func _draw_choice_overlay" in gameplay_script
    assert "func _draw_outcome_overlay" in gameplay_script
    destination = tmp_path / "product"
    GODOT_GAMEPLAY_TOOLPACK.execution_adapter.materialize(first, destination)
    assert {path.as_posix() for path in destination.rglob("*") if path.is_file()} == {
        (destination / path).as_posix() for path in [*first.files, first.asset.path, first.sprite_atlas.path]
    }
    assert hashlib.sha256((destination / first.asset.path).read_bytes()).hexdigest() == first.asset.sha256


def test_gameplay_plan_rejects_unknown_ability_owner_and_impossible_level_schedule() -> None:
    raw = gameplay_plan().model_dump(mode="json")
    raw["abilities"][0]["owner_hero_id"] = "missing"
    with pytest.raises(ValueError, match="unknown heroes"):
        GodotGameplayPlan.model_validate(raw)


def test_explicit_trinity_requirements_are_plan_and_probe_authority() -> None:
    criteria = explicit_gameplay_criteria(
        "Create a 10-minute run with levels about once per minute; tank, damage, and healer in order; "
        "one upgrade and two alternative professions; combined health, attack, defense, attack speed, and movement speed; stored resurrection."
    )
    raw = gameplay_plan().model_dump(mode="json")
    raw.update({"session_seconds": 600, "level_count": 10, "level_interval_seconds": 60})
    plan = GodotGameplayPlan.model_validate(raw)
    validate_gameplay_plan_requirements(plan, criteria)
    wrong = plan.model_copy(update={"session_seconds": 120})
    with pytest.raises(PermissionError, match="10-minute"):
        validate_gameplay_plan_requirements(wrong, criteria)
    raw = gameplay_plan().model_dump(mode="json")
    raw["session_seconds"] = 30
    with pytest.raises(ValueError, match="level schedule"):
        GodotGameplayPlan.model_validate(raw)


def test_explicit_playability_requirements_bind_visible_gameplay_feedback() -> None:
    criteria = explicit_gameplay_criteria(
        "Show a start button and 10:00 countdown, brighter background, green monsters, "
        "hero attack animation and attack range, level choice text, defeat message, and restart prompt."
    )
    assert any("START gate" in criterion for criterion in criteria)
    assert any("decreasing session countdown" in criterion for criterion in criteria)
    assert any("visible motion" in criterion for criterion in criteria)
    assert any("green hostile visual family" in criterion for criterion in criteria)
    assert any("brighter readable background" in criterion for criterion in criteria)
    assert any("next available input" in criterion for criterion in criteria)


def test_explicit_combat_requirements_bind_distinct_attacks_and_cooldowns() -> None:
    criteria = explicit_gameplay_criteria(
        "The first enemy at level 1 must be beatable. Every hero needs a visible basic attack; "
        "skills need cooldowns and separate effects, with a heal effect and enemy attack effect."
    )
    assert any("first level-one enemy" in criterion for criterion in criteria)
    assert any("Every hero independently" in criterion for criterion in criteria)
    assert any("declared cooldowns" in criterion for criterion in criteria)
    assert any("green restorative effect" in criterion for criterion in criteria)
    assert any("bounded cadence" in criterion for criterion in criteria)


def test_gameplay_toolpack_rejects_bundle_or_asset_tampering(tmp_path) -> None:
    approved = artifact()
    changed = dict(approved.files)
    changed["README.md"] += "unauthorized\n"
    tampered = approved.model_copy(update={"files": changed})
    with pytest.raises(PermissionError, match="bundle digest changed"):
        GODOT_GAMEPLAY_TOOLPACK.execution_adapter.materialize(tampered, tmp_path / "tampered")
    destination = tmp_path / "product"
    GODOT_GAMEPLAY_TOOLPACK.execution_adapter.materialize(approved, destination)
    (destination / approved.asset.path).write_bytes(png(257, 256))
    with pytest.raises(PermissionError, match="asset changed"):
        GODOT_GAMEPLAY_TOOLPACK.evidence_adapter.verify(
            approved, destination, tmp_path / "evidence", ["The gameplay is visible."],
        )


def test_real_godot_gameplay_probe_and_render(tmp_path, monkeypatch) -> None:
    executable = r"E:\memory R data\archive_20260818_first_priority\C-tmp\khalinos-engine-bakeoff\godot\Godot_v4.7.1-stable_win64.exe"
    monkeypatch.setenv("KHALINOS_GODOT_EXECUTABLE", executable)
    approved = artifact()
    product = tmp_path / "product"
    evidence = tmp_path / "evidence"
    GODOT_GAMEPLAY_TOOLPACK.execution_adapter.materialize(approved, product)
    receipt = GODOT_GAMEPLAY_TOOLPACK.evidence_adapter.verify(
        approved,
        product,
        evidence,
        ["The formation moves, enemies spawn, abilities trigger, and level choices appear."],
    )
    assert receipt.passed is True
    assert all(receipt.checks.values())
    assert (evidence / "godot-gameplay-probe.json").is_file()
    assert receipt.screenshot_names


class StubGameplayEvidenceAdapter:
    adapter_id = GODOT_GAMEPLAY_MANIFEST.evidence.adapter_id

    def verify(self, artifact, root, evidence_dir, acceptance_criteria):
        assert (root / "scenes" / "gameplay.tscn").is_file()
        evidence_dir.mkdir(parents=True, exist_ok=True)
        screenshot = evidence_dir / "godot-gameplay-render00000002.png"
        screenshot.write_bytes(png())
        return DeterministicEvidence(
            passed=True,
            checks={"gameplay_probe": True, "display_render": True},
            issues=[],
            screenshot_names=[screenshot.name],
            criterion_evidence={item: ["Digest-bound gameplay runtime evidence passed."] for item in acceptance_criteria},
        )


class StubGameplayTeam:
    def __init__(self) -> None:
        self.call_count = 0
        self.sprite_feedback: list[tuple[str, ...]] = []
        self.sprite_gate_calls = 0
        self.reject_first_sprite_gate = False
        self.concepts = [
            VisualConcept(
                candidate_id=f"V{index}",
                name=name,
                design_thesis=f"{name} creates a distinct readable survival field for the complete bounded gameplay loop.",
                composition="The party remains central while threats arrive through a broad environmental perimeter.",
                typography="Compact high-contrast status labels preserve gameplay readability.",
                palette=palette,
                interaction_emphasis="Movement, health, enemies, and level choice remain visually dominant.",
                anti_goals=["generic dashboard cards", "text baked into imagery"],
            )
            for index, (name, palette) in enumerate([
                ("Verdant Ruins", ["moss", "sandstone", "ember"]),
                ("Moonlit Archive", ["midnight", "silver", "cyan"]),
                ("Ashen Frontier", ["charcoal", "ochre", "crimson"]),
            ], start=1)
        ]

    async def plan_godot_gameplay(self, payload):
        self.call_count += 2
        criteria = payload["approved_brief"]["acceptance_criteria"]
        return GodotGameplayProjectPlan(
            quest_plan=QuestPlan(
                product_summary="A bounded playable Godot 2D survival gameplay vertical slice.",
                architecture_decision="Use the trusted data-driven gameplay compiler and runtime probes.",
                quests=[
                    QuestSpec(quest_id="Q1", objective="Build and prove the formation survival loop.", acceptance_criteria=[criteria[0]], evidence_required=["Gameplay probe and render."]),
                    QuestSpec(quest_id="Q2", objective="Build and prove automatic progression.", acceptance_criteria=[criteria[1]], evidence_required=["Gameplay probe and render."], depends_on=["Q1"]),
                ],
            ),
            gameplay=gameplay_plan(),
        )

    async def plan_visuals(self, payload):
        self.call_count += 1
        return VisualConceptPlan(shared_contract="Three distinct readable environmental foundations for the same bounded gameplay loop.", candidates=self.concepts)

    async def make_visual_asset(self, brief, concept):
        self.call_count += 1
        return trusted_png_asset(png())

    async def verify_visual_asset(self, candidate_id, asset, concept):
        self.call_count += 1
        return VisualAssetGate(candidate_id=candidate_id, approved=True, contains_text_or_glyphs=False, contains_interface_elements=False, contains_logo_or_watermark=False, rationale="The image is a clean environmental foundation without text or interface elements.")

    async def make_sprite_atlas(self, brief, concept, plan, feedback=()):
        self.call_count += 1
        self.sprite_feedback.append(tuple(feedback))
        return sprite_asset(plan)

    async def verify_sprite_atlas(self, plan, asset, concept):
        self.call_count += 1
        self.sprite_gate_calls += 1
        approved = not (self.reject_first_sprite_gate and self.sprite_gate_calls == 1)
        return SpriteAtlasGate(
            approved=approved,
            slot_count_matches=True,
            roles_are_distinguishable=True,
            style_is_consistent=True,
            contains_text_or_glyphs=False,
            contains_interface_elements=False,
            contains_logo_or_watermark=False,
            has_clipped_or_overlapping_sprites=False,
            all_characters_complete=True,
            all_required_equipment_preserved=True,
            background_residue_absent=approved,
            slot_findings=[
                SpriteSlotVisualFinding(
                    sprite_id=slot.sprite_id,
                    complete_full_body=True,
                    required_equipment_preserved=True,
                    background_residue_absent=approved,
                    role_is_readable=True,
                    issue=None if approved else "Background residue is present.",
                )
                for slot in plan.slots
            ],
            issues=[] if approved else ["Remove checker patterns and platforms from every sprite."],
            rationale=(
                "Every planned character occupies one distinct and coherent sprite slot without forbidden content."
                if approved else "The first atlas contains a repeated forbidden background artifact."
            ),
        )

    async def select_visual(self, payload, screenshots):
        self.call_count += 1
        assessments = [
            VisualAssessment(candidate_id=candidate_id, contract_alignment=score, visual_hierarchy=score, distinctiveness=score, interaction_clarity=score, craft_and_cohesion=score, strengths=["Clear gameplay field."])
            for candidate_id, score in [("V1", 10), ("V2", 9), ("V3", 8)]
        ]
        return VisualSelection(assessments=assessments, selected_candidate_id="V1", rationale="V1 has the strongest readable hierarchy and contract alignment for this gameplay slice.")

    async def verify_godot(self, payload):
        self.call_count += 1
        criterion = payload["quest"]["acceptance_criteria"][0]
        return AgentVerification(findings=[CriterionFinding(criterion=criterion, passed=True, evidence="The deterministic gameplay receipt directly proves this criterion.")], verdict="PASS")


async def test_gameplay_workflow_binds_visual_selection_runtime_and_quest_receipts(tmp_path) -> None:
    toolpack = RegisteredToolPack(
        manifest=GODOT_GAMEPLAY_MANIFEST,
        execution_adapter=GODOT_GAMEPLAY_TOOLPACK.execution_adapter,
        evidence_adapter=StubGameplayEvidenceAdapter(),
    )
    binding = toolpack.binding()
    criteria = [
        "The three-hero formation moves while enemies spawn and attack.",
        "Automatic abilities, shared health, and level choices work during the session.",
    ]
    brief = UserBrief(
        project_name="Trinity Trial",
        goal="Create a bounded 2D top-down survival vertical slice in Godot.",
        acceptance_criteria=criteria,
        max_quests=2,
        toolpack_binding=binding,
        authorized_output_files=list(toolpack.manifest.output.authorized_paths),
    )
    run_id = "f" * 32
    store = LocalRunStore(tmp_path)
    store.create(RunRecord(run_id=run_id, status=RunStatus.QUEUED, brief_sha256=canonical_sha256(brief), toolpack_binding=binding, message="Queued.", work_mode="new_product_build"), brief)
    team = StubGameplayTeam()
    team.reject_first_sprite_gate = True
    result = await execute_godot_gameplay_run(run_id, store=store, team=team, registry=ToolPackRegistry([toolpack]))
    assert result.status == RunStatus.PASSED
    assert team.sprite_gate_calls == 2
    assert team.sprite_feedback == [(), ("Remove checker patterns and platforms from every sprite.",)]
    assert (tmp_path / "runs" / run_id / "sprites" / "attempts" / "1" / "gate.json").is_file()
    assert (tmp_path / "runs" / run_id / "sprites" / "attempts" / "2" / "gate.json").is_file()
    assert len(result.completed_receipt_ids) == 3
    assert (tmp_path / "runs" / run_id / "visuals" / "selection_receipt.json").is_file()
    assert (tmp_path / "runs" / run_id / "final" / "source.zip").is_file()
    assert (tmp_path / "runs" / run_id / "sprites" / "final" / "deterministic_evidence.json").is_file()
