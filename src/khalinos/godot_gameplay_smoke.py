"""Cloud qualification entry point for the approved Godot Gameplay ToolPack."""

from __future__ import annotations

import json
import io
import struct
import tempfile
import zlib
from pathlib import Path
from PIL import Image, ImageDraw

from khalinos.godot_gameplay import (
    GameplayAbility, GameplayEnemy, GameplayHero, GameplayProfession, GameplayProfessionRoster, GodotGameplayPlan,
    compile_godot_gameplay,
    derive_sprite_atlas_plan,
)
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.models import VisualConcept
from khalinos.visual_assets import trusted_png_asset
from khalinos.sprite_assets import (
    SPRITE_SEGMENTATION_CONTRACT,
    ApprovedSpriteSegmenter,
    normalize_sprite_atlas,
    verify_sprite_segmentation_model,
)


def _png(width: int = 256, height: int = 256) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    rows = b"".join(
        b"\x00" + b"".join(bytes(((x * 3) % 256, (y * 2) % 256, (x + y) % 256, 255)) for x in range(width))
        for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    plan = GodotGameplayPlan(
        project_name="KHALINOS Gameplay Qualification",
        session_seconds=600,
        heroes=(
            GameplayHero(hero_id="warrior", label="Warrior", role="tank", color_hex="D9A441", health=120, attack=20, defense=12, attack_speed=1.0, move_speed=60),
            GameplayHero(hero_id="archer", label="Archer", role="damage", color_hex="74B86A", health=80, attack=30, defense=5, attack_speed=1.4, move_speed=70),
            GameplayHero(hero_id="priest", label="Priest", role="support", color_hex="8AB4D8", health=90, attack=8, defense=8, attack_speed=0.8, move_speed=60),
        ),
        enemies=(
            GameplayEnemy(enemy_id="goblin", label="Goblin", color_hex="79A94B", health=15, damage=5, speed=60, record_value=4, spawn_weight=60),
            GameplayEnemy(enemy_id="orc", label="Orc", color_hex="A36E44", health=30, damage=8, speed=45, record_value=8, spawn_weight=30),
            GameplayEnemy(enemy_id="troll", label="Troll", color_hex="6F7550", health=60, damage=12, speed=30, record_value=12, spawn_weight=10),
        ),
        abilities=(
            GameplayAbility(ability_id="sweep", label="Sweep", owner_hero_id="warrior", kind="damage", cooldown_seconds=1, power=20, radius=120),
            GameplayAbility(ability_id="volley", label="Volley", owner_hero_id="archer", kind="damage", cooldown_seconds=1, power=18, radius=180),
            GameplayAbility(ability_id="prayer", label="Prayer", owner_hero_id="priest", kind="heal", cooldown_seconds=2, power=15, radius=120),
            GameplayAbility(ability_id="revive", label="Stored Resurrection", owner_hero_id="priest", kind="resurrection", cooldown_seconds=3, power=1, radius=120),
        ),
        level_count=10,
        level_interval_seconds=60,
        choices_per_level=3,
        profession_rosters=(
            GameplayProfessionRoster(role="tank", starting_profession_id="warrior", professions=(
                GameplayProfession(profession_id="warrior", label="Warrior", role="tank", stat_focus="balanced"),
                GameplayProfession(profession_id="shield_warrior", label="Shield Warrior", role="tank", stat_focus="defense"),
                GameplayProfession(profession_id="axe_warrior", label="Axe Warrior", role="tank", stat_focus="attack"),
            )),
            GameplayProfessionRoster(role="damage", starting_profession_id="archer", professions=(
                GameplayProfession(profession_id="archer", label="Archer", role="damage", stat_focus="balanced"),
                GameplayProfession(profession_id="crossbowman", label="Crossbowman", role="damage", stat_focus="move_speed"),
                GameplayProfession(profession_id="longbowman", label="Longbowman", role="damage", stat_focus="attack"),
            )),
            GameplayProfessionRoster(role="support", starting_profession_id="priest", professions=(
                GameplayProfession(profession_id="priest", label="Priest", role="support", stat_focus="utility"),
                GameplayProfession(profession_id="paladin", label="Paladin", role="support", stat_focus="defense"),
                GameplayProfession(profession_id="dark_priest", label="Dark Priest", role="support", stat_focus="attack"),
            )),
        ),
        resurrection_capacity=1,
        deterministic_seed=20260819,
    )
    concept = VisualConcept(
        candidate_id="V1",
        name="Qualification Field",
        design_thesis="A clean environmental field verifies the complete bounded gameplay rendering path.",
        composition="The controlled formation stays central while threats enter from the perimeter.",
        typography="Minimal status typography preserves gameplay readability.",
        palette=["moss", "sandstone", "ember"],
        interaction_emphasis="Movement, threats, health, and progression remain legible.",
        anti_goals=["generic dashboard cards", "text baked into imagery"],
    )
    sprite_plan = derive_sprite_atlas_plan(plan)
    image = Image.new("RGBA", (1024, 768), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    colors = ["#d9a441", "#74b86a", "#8ab4d8", "#79a94b", "#a36e44", "#6f7550"]
    for slot, color in zip(sprite_plan.slots, colors, strict=True):
        left, top, width, height = slot.region()
        draw.ellipse((left + 72, top + 48, left + width - 72, top + height - 48), fill=color, outline="#2b271f", width=6)
    output = io.BytesIO()
    image.save(output, format="PNG")
    sprite_atlas = normalize_sprite_atlas(output.getvalue(), sprite_plan)
    model_path = verify_sprite_segmentation_model()
    segmented_probe = ApprovedSpriteSegmenter(model_path)(output.getvalue())
    segmented_probe_image = Image.open(io.BytesIO(segmented_probe)).convert("RGBA")
    if segmented_probe_image.size != (1024, 768):
        raise RuntimeError("approved sprite segmentation runtime changed the probe dimensions")
    artifact = compile_godot_gameplay(
        plan,
        concept,
        trusted_png_asset(_png()),
        sprite_plan,
        sprite_atlas,
        require_sprite_atlas=True,
    )
    binding = APPROVED_TOOLPACKS.binding_for("godot.gameplay")
    toolpack = APPROVED_TOOLPACKS.resolve(binding)
    with tempfile.TemporaryDirectory(prefix="khalinos-gameplay-cloud-") as temporary:
        root = Path(temporary) / "product"
        evidence = Path(temporary) / "evidence"
        toolpack.execution_adapter.materialize(artifact, root)
        receipt = toolpack.evidence_adapter.verify(
            artifact,
            root,
            evidence,
            ["The bounded gameplay mechanics and rendered result execute in the approved runtime."],
        )
        result = {
            "passed": receipt.passed,
            "checks": receipt.checks,
            "issues": receipt.issues,
            "screenshots": receipt.screenshot_names,
            "toolpack_binding": binding.model_dump(mode="json"),
            "artifact_sha256": artifact.bundle_sha256,
            "sprite_segmentation_contract_sha256": SPRITE_SEGMENTATION_CONTRACT.sha256(),
            "sprite_segmentation_model_sha256": SPRITE_SEGMENTATION_CONTRACT.model_sha256,
            "sprite_segmentation_inference": True,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if not receipt.passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
