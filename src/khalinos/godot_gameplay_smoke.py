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
    GameplayAbility, GameplayEnemy, GameplayHero, GodotGameplayPlan,
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
        session_seconds=30,
        heroes=(GameplayHero(hero_id="guardian", label="Guardian", role="tank", color_hex="D9A441", health=120, attack=20, defense=12, move_speed=180),),
        enemies=(GameplayEnemy(enemy_id="raider", label="Raider", color_hex="79A94B", health=15, damage=5, speed=60, record_value=4, spawn_weight=100),),
        abilities=(GameplayAbility(ability_id="sweep", label="Sweep", owner_hero_id="guardian", kind="damage", cooldown_seconds=1, power=20, radius=120),),
        level_count=2,
        level_interval_seconds=15,
        choices_per_level=2,
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
    draw.ellipse((72, 48, 184, 208), fill="#d9a441", outline="#2b271f", width=6)
    draw.ellipse((328, 48, 440, 208), fill="#79a94b", outline="#2b271f", width=6)
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
