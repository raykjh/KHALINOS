"""One-shot Cloud qualification for the complete approved Sprite Asset path."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from khalinos.agents import AgentTeam
from khalinos.godot_gameplay import (
    GameplayAbility,
    GameplayEnemy,
    GameplayHero,
    GodotGameplayPlan,
    compile_godot_gameplay,
    derive_sprite_atlas_plan,
)
from khalinos.models import UserBrief, VisualConcept
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.sprite_assets import SPRITE_SEGMENTATION_CONTRACT
from khalinos.visual_assets import trusted_png_asset
from khalinos.godot_gameplay_smoke import _png


async def qualify() -> dict[str, object]:
    gameplay = GodotGameplayPlan(
        project_name="KHALINOS Sprite Qualification",
        session_seconds=30,
        heroes=(
            GameplayHero(
                hero_id="guardian",
                label="Guardian",
                role="tank",
                color_hex="D9A441",
                health=120,
                attack=20,
                defense=12,
                move_speed=180,
            ),
        ),
        enemies=(
            GameplayEnemy(
                enemy_id="raider",
                label="Raider",
                color_hex="79A94B",
                health=15,
                damage=5,
                speed=60,
                record_value=4,
                spawn_weight=100,
            ),
        ),
        abilities=(
            GameplayAbility(
                ability_id="sweep",
                label="Sweep",
                owner_hero_id="guardian",
                kind="damage",
                cooldown_seconds=1,
                power=20,
                radius=120,
            ),
        ),
        level_count=2,
        level_interval_seconds=15,
        choices_per_level=2,
        deterministic_seed=20260820,
    )
    brief = UserBrief(
        project_name=gameplay.project_name,
        goal=(
            "Create one bounded top-down Godot qualification scene with a complete armored guardian "
            "and one complete hostile raider rendered as distinct, production-quality fantasy sprites."
        ),
        acceptance_criteria=[
            "The guardian and raider retain complete bodies and their role-defining equipment.",
            "The guardian and raider are distinct and visible in the running Godot scene.",
        ],
        authorized_output_files=["assets/sprite-atlas.png"],
    )
    concept = VisualConcept(
        candidate_id="V1",
        name="Verdant Qualification Field",
        design_thesis=(
            "Polished painterly fantasy sprites with strong silhouettes, restrained texture, "
            "and coherent warm rim lighting."
        ),
        composition="Each isolated character reads clearly at compact top-down gameplay scale.",
        typography="No typography appears inside generated sprite sources.",
        palette=["moss green", "weathered bronze", "warm parchment", "ember orange"],
        interaction_emphasis="The hero role and enemy threat remain immediately distinguishable.",
        anti_goals=["photorealism", "chibi proportions", "text", "scenery", "multiple characters"],
    )
    sprite_plan = derive_sprite_atlas_plan(gameplay)
    team = AgentTeam()
    sprite_atlas = await team.make_sprite_atlas(brief, concept, sprite_plan)
    sprite_gate = await team.verify_sprite_atlas(sprite_plan, sprite_atlas, concept)
    if not sprite_gate.approved:
        raise RuntimeError(
            "independent Sprite Atlas Gate rejected the qualification atlas: "
            + "; ".join(sprite_gate.issues)
        )

    artifact = compile_godot_gameplay(
        gameplay,
        concept,
        trusted_png_asset(_png()),
        sprite_plan,
        sprite_atlas,
        require_sprite_atlas=True,
    )
    binding = APPROVED_TOOLPACKS.binding_for("godot.gameplay")
    toolpack = APPROVED_TOOLPACKS.resolve(binding)
    with tempfile.TemporaryDirectory(prefix="khalinos-sprite-qualification-") as temporary:
        root = Path(temporary) / "product"
        evidence = Path(temporary) / "evidence"
        toolpack.execution_adapter.materialize(artifact, root)
        receipt = toolpack.evidence_adapter.verify(
            artifact,
            root,
            evidence,
            brief.acceptance_criteria,
        )
    if not receipt.passed:
        raise RuntimeError("sprite-bound Godot qualification failed: " + "; ".join(receipt.issues))
    return {
        "passed": True,
        "model_calls": team.call_count,
        "toolpack_binding": binding.model_dump(mode="json"),
        "sprite_atlas_sha256": sprite_atlas.sha256,
        "sprite_gate": sprite_gate.model_dump(mode="json"),
        "sprite_segmentation_contract_sha256": SPRITE_SEGMENTATION_CONTRACT.sha256(),
        "sprite_segmentation_model_sha256": SPRITE_SEGMENTATION_CONTRACT.model_sha256,
        "artifact_sha256": artifact.bundle_sha256,
        "runtime_checks": receipt.checks,
        "screenshots": receipt.screenshot_names,
    }


def main() -> None:
    print(json.dumps(asyncio.run(qualify()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
