from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw, ImageOps

from khalinos.sprite_assets import (
    SpriteAtlasPlan,
    SpriteSlot,
    compose_sprite_atlas,
    generate_sprite_atlas,
    normalize_sprite_atlas,
    normalize_sprite_source,
    sprite_source_prompt,
    verify_sprite_segmentation_model,
)
from khalinos.models import SpriteAtlasGate, SpriteSlotVisualFinding


def plan() -> SpriteAtlasPlan:
    return SpriteAtlasPlan(slots=(
        SpriteSlot(sprite_id="warrior", kind="hero", label="Warrior", visual_role="tank hero", slot_index=0),
        SpriteSlot(sprite_id="goblin", kind="enemy", label="Goblin", visual_role="hostile enemy", slot_index=1),
    ))


def atlas(*, spill: bool = False, unused: bool = False) -> bytes:
    image = Image.new("RGBA", (1024, 768), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((72, 48, 184, 208), fill="#d9a441")
    draw.ellipse((328, 48, 440, 208), fill="#79a94b")
    if spill:
        draw.rectangle((0, 80, 20, 180), fill="#ffffff")
    if unused:
        draw.ellipse((584, 48, 696, 208), fill="#a36e44")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def atlas_with_distinct_cell_backgrounds() -> bytes:
    image = Image.new("RGBA", (1024, 768), "#f0d8bc")
    draw = ImageDraw.Draw(image)
    for index in range(12):
        left = (index % 4) * 256
        top = (index // 4) * 256
        shade = 218 + (index % 3) * 8
        draw.rectangle((left, top, left + 255, top + 255), fill=(shade, shade - 12, shade - 25, 255))
    draw.ellipse((72, 48, 184, 208), fill="#d9a441")
    draw.ellipse((328, 48, 440, 208), fill="#79a94b")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def source(color: str, *, touches_edge: bool = False) -> bytes:
    image = Image.new("RGBA", (1024, 1024), "#ff00ff")
    draw = ImageDraw.Draw(image)
    bounds = (0, 180, 640, 900) if touches_edge else (250, 140, 774, 900)
    draw.ellipse(bounds, fill=color, outline="#221f1a", width=16)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def empty_source() -> bytes:
    image = Image.new("RGBA", (1024, 1024), "#ff00ff")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def source_on_gradient(color: str) -> bytes:
    gradient = Image.linear_gradient("L").resize((1024, 1024))
    image = ImageOps.colorize(gradient, black=(205, 184, 161), white=(244, 225, 204)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.ellipse((250, 140, 774, 900), fill=color, outline="#221f1a", width=16)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def source_with_boundary_artifact(color: str) -> bytes:
    image = Image.new("RGBA", (1024, 1024), "#ff00ff")
    draw = ImageDraw.Draw(image)
    draw.ellipse((250, 140, 774, 900), fill=color, outline="#221f1a", width=16)
    draw.rectangle((4, 300, 10, 700), fill="#42617a")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def small_source(color: str) -> bytes:
    image = Image.new("RGBA", (1024, 1024), "#ff00ff")
    draw = ImageDraw.Draw(image)
    draw.ellipse((430, 390, 594, 650), fill=color, outline="#221f1a", width=8)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_normalization_binds_exact_slots_and_transparency() -> None:
    asset = normalize_sprite_atlas(atlas(), plan())
    assert asset.path == "assets/sprite-atlas.png"
    assert asset.width == 1024 and asset.height == 768


def test_normalization_trustfully_resamples_official_1k_four_by_three_output() -> None:
    source = Image.open(io.BytesIO(atlas())).resize((1200, 896), Image.Resampling.NEAREST)
    output = io.BytesIO()
    source.save(output, format="PNG")
    asset = normalize_sprite_atlas(output.getvalue(), plan())
    assert asset.width == 1024 and asset.height == 768


def test_normalization_removes_distinct_flat_background_per_cell() -> None:
    asset = normalize_sprite_atlas(atlas_with_distinct_cell_backgrounds(), plan())
    normalized = Image.open(io.BytesIO(asset.bytes())).convert("RGBA")
    assert normalized.getpixel((700, 100))[3] == 0


def test_individual_sources_are_normalized_then_composed_in_fixed_order() -> None:
    approved = plan()
    sprites = tuple(
        normalize_sprite_source(source(color), slot)
        for slot, color in zip(approved.slots, ("#d9a441", "#79a94b"), strict=True)
    )
    asset = compose_sprite_atlas(approved, sprites)
    image = Image.open(io.BytesIO(asset.bytes())).convert("RGBA")
    assert image.getchannel("A").crop((0, 0, 256, 256)).getbbox() is not None
    assert image.getchannel("A").crop((256, 0, 512, 256)).getbbox() is not None
    assert image.getchannel("A").crop((512, 0, 768, 256)).getbbox() is None


def test_individual_source_rejects_missing_character() -> None:
    with pytest.raises(ValueError, match="contains no isolated central character"):
        normalize_sprite_source(empty_source(), plan().slots[0])


def test_individual_source_removes_boundary_connected_gradient_background() -> None:
    sprite = normalize_sprite_source(source_on_gradient("#d9a441"), plan().slots[0])
    image = Image.open(io.BytesIO(sprite.bytes())).convert("RGBA")
    assert image.getpixel((0, 0))[3] == 0
    assert image.getchannel("A").getbbox() is not None


def test_individual_source_discards_disconnected_boundary_artifact() -> None:
    sprite = normalize_sprite_source(source_with_boundary_artifact("#d9a441"), plan().slots[0])
    image = Image.open(io.BytesIO(sprite.bytes())).convert("RGBA")
    assert image.getpixel((0, 128))[3] == 0
    assert image.getchannel("A").getbbox() is not None


def test_individual_source_normalizes_valid_small_subject_to_cell_scale() -> None:
    sprite = normalize_sprite_source(small_source("#d9a441"), plan().slots[0])
    image = Image.open(io.BytesIO(sprite.bytes())).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    assert bbox is not None
    assert max(bbox[2] - bbox[0], bbox[3] - bbox[1]) == 208


def test_individual_prompt_assigns_one_character_without_atlas_layout() -> None:
    from khalinos.models import UserBrief, VisualConcept

    brief = UserBrief(
        project_name="Trinity Trial",
        goal="Create one bounded top-down survival game with a readable fantasy party and enemies.",
        acceptance_criteria=["Heroes are distinct.", "Enemies are distinct."],
        authorized_output_files=["assets/sprite-atlas.png"],
    )
    concept = VisualConcept(
        candidate_id="V1", name="Verdant Ruins",
        design_thesis="Painterly fantasy silhouettes share one coherent material and lighting language.",
        composition="The party is clear at compact gameplay scale.",
        typography="UI typography remains outside generated imagery.",
        palette=["moss", "gold", "stone"],
        interaction_emphasis="Characters remain distinct.",
        anti_goals=["text", "scenery"],
    )
    prompt = sprite_source_prompt(brief, concept, plan().slots[0])
    assert "exactly one isolated" in prompt
    assert "occupy 45% to 65%" in prompt
    assert "continuous high-contrast outer contour" in prompt
    assert "4-column" not in prompt


def test_generation_segments_every_source_before_normalization(monkeypatch) -> None:
    from khalinos.models import UserBrief, VisualConcept
    import khalinos.sprite_assets as module

    brief = UserBrief(
        project_name="Trinity Trial",
        goal="Create one bounded top-down survival game with a readable fantasy party and enemies.",
        acceptance_criteria=["Heroes are distinct.", "Enemies are distinct."],
        authorized_output_files=["assets/sprite-atlas.png"],
    )
    concept = VisualConcept(
        candidate_id="V1", name="Verdant Ruins",
        design_thesis="Painterly fantasy silhouettes share one coherent material and lighting language.",
        composition="The party is clear at compact gameplay scale.",
        typography="UI typography remains outside generated imagery.",
        palette=["moss", "gold", "stone"],
        interaction_emphasis="Characters remain distinct.",
        anti_goals=["text", "scenery"],
    )
    payloads = iter((source("#d9a441"), source("#79a94b")))

    monkeypatch.setattr(module.genai, "Client", lambda **kwargs: object())
    monkeypatch.setattr(
        module,
        "_generate_with_transient_retry",
        lambda *args, **kwargs: SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
            SimpleNamespace(inline_data=SimpleNamespace(mime_type="image/png", data=next(payloads)))
        ]))]),
    )
    segmented: list[bytes] = []
    def segment(payload: bytes) -> bytes:
        segmented.append(payload)
        return payload
    calls: list[int] = []
    asset = generate_sprite_atlas(
        brief,
        concept,
        plan(),
        on_model_call=lambda: calls.append(1),
        segment_source=segment,
    )
    assert asset.path == "assets/sprite-atlas.png"
    assert len(calls) == 2
    assert len(segmented) == 2


def test_generation_retries_one_rejected_source_once_with_bounded_feedback(monkeypatch) -> None:
    from khalinos.models import UserBrief, VisualConcept
    import khalinos.sprite_assets as module

    brief = UserBrief(
        project_name="Trinity Trial",
        goal="Create one bounded top-down survival game with readable characters.",
        acceptance_criteria=["Heroes are distinct.", "Enemies are distinct."],
        authorized_output_files=["assets/sprite-atlas.png"],
    )
    concept = VisualConcept(
        candidate_id="V1", name="Verdant Ruins",
        design_thesis="Painterly fantasy silhouettes share one coherent material language.",
        composition="The party is clear at compact gameplay scale.",
        typography="UI typography remains outside generated imagery.",
        palette=["moss", "gold", "stone"],
        interaction_emphasis="Characters remain distinct.",
        anti_goals=["text", "scenery"],
    )
    payloads = iter((empty_source(), source("#d9a441"), source("#79a94b")))
    prompts: list[str] = []

    monkeypatch.setattr(module.genai, "Client", lambda **kwargs: object())
    def generate(client, prompt, **kwargs):
        del client, kwargs
        prompts.append(prompt)
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
            SimpleNamespace(inline_data=SimpleNamespace(mime_type="image/png", data=next(payloads)))
        ]))])
    monkeypatch.setattr(module, "_generate_with_transient_retry", generate)
    calls: list[int] = []

    asset = generate_sprite_atlas(
        brief,
        concept,
        plan(),
        on_model_call=lambda: calls.append(1),
        segment_source=lambda payload: payload,
    )

    assert asset.path == "assets/sprite-atlas.png"
    assert len(calls) == 3
    assert len(prompts) == 3
    assert "rejected by deterministic normalization" in prompts[1]
    assert "previous rejected-source issue" not in prompts[2].casefold()


def test_segmentation_model_verification_fails_closed_when_weight_is_missing(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="model is missing"):
        verify_sprite_segmentation_model(tmp_path / "isnet-anime.onnx")


def test_normalization_rejects_gutter_spill_and_unassigned_character() -> None:
    with pytest.raises(ValueError, match="protected gutter"):
        normalize_sprite_atlas(atlas(spill=True), plan())
    with pytest.raises(ValueError, match="unassigned sprite atlas cell"):
        normalize_sprite_atlas(atlas(unused=True), plan())


def test_plan_rejects_noncontiguous_or_duplicate_slots() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        SpriteAtlasPlan(slots=(
            SpriteSlot(sprite_id="warrior", kind="hero", label="Warrior", visual_role="tank hero", slot_index=0),
            SpriteSlot(sprite_id="goblin", kind="enemy", label="Goblin", visual_role="hostile enemy", slot_index=2),
        ))


def test_visual_completeness_gate_cannot_approve_erased_character_parts() -> None:
    finding = SpriteSlotVisualFinding(
        sprite_id="warrior",
        complete_full_body=False,
        required_equipment_preserved=False,
        background_residue_absent=True,
        role_is_readable=False,
        issue="The body and sword were materially erased.",
    )
    with pytest.raises(ValueError, match="approval must match"):
        SpriteAtlasGate(
            approved=True,
            slot_count_matches=True,
            roles_are_distinguishable=True,
            style_is_consistent=True,
            contains_text_or_glyphs=False,
            contains_interface_elements=False,
            contains_logo_or_watermark=False,
            has_clipped_or_overlapping_sprites=False,
            all_characters_complete=False,
            all_required_equipment_preserved=False,
            background_residue_absent=True,
            slot_findings=[finding],
            issues=["The warrior is incomplete."],
            rationale="The atlas cannot pass because a required character and its weapon are incomplete.",
        )
