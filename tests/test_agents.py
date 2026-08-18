from __future__ import annotations

from khalinos.agents import AgentTeam, VISUAL_MAKER_INSTRUCTION
from khalinos.sixsense import SIXSENSE_INSTRUCTION


def test_artifact_agents_have_capacity_for_the_bounded_complete_bundle() -> None:
    team = AgentTeam()
    assert team.maker.generate_content_config.max_output_tokens == 49_152
    assert team.repairer.generate_content_config.max_output_tokens == 49_152
    assert team.owner.generate_content_config.max_output_tokens == 8_192
    assert team.verifier.generate_content_config.max_output_tokens == 8_192
    assert team.visual_director.generate_content_config.max_output_tokens == 8_192
    assert team.visual_maker.generate_content_config.max_output_tokens == 49_152
    assert team.visual_verifier.generate_content_config.max_output_tokens == 8_192


def test_sixsense_visual_instruction_rejects_generic_template_defaults() -> None:
    assert "inspect supplied reference images concretely" in SIXSENSE_INSTRUCTION
    assert "Do not use generic" in SIXSENSE_INSTRUCTION
    assert "explicit anti-goals" in SIXSENSE_INSTRUCTION


def test_sixsense_questions_preserve_real_user_choice_and_professional_defaults() -> None:
    assert "two to four mutually exclusive answer_options" in SIXSENSE_INSTRUCTION
    assert "no more than\n48 characters each" in SIXSENSE_INSTRUCTION
    assert "no more than three" in SIXSENSE_INSTRUCTION
    assert "established best practices" in SIXSENSE_INSTRUCTION
    assert "first-click safety" in SIXSENSE_INSTRUCTION
    assert "strongest suitable standard" in SIXSENSE_INSTRUCTION
    assert "standard modes, presets, and quality features" in SIXSENSE_INSTRUCTION


def test_visual_maker_has_exact_runtime_and_accessibility_contract() -> None:
    assert '{"journeys":[...]}' in VISUAL_MAKER_INSTRUCTION
    assert '{"click":"CSS selector"}' in VISUAL_MAKER_INSTRUCTION
    assert "Do not use type, selector, text, or key fields" in VISUAL_MAKER_INSTRUCTION
    assert "explicit label or aria-label" in VISUAL_MAKER_INSTRUCTION
