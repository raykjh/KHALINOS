from __future__ import annotations

from khalinos.agents import AgentTeam
from khalinos.sixsense import SIXSENSE_INSTRUCTION


def test_artifact_agents_have_capacity_for_the_bounded_complete_bundle() -> None:
    team = AgentTeam()
    assert team.maker.generate_content_config.max_output_tokens == 49_152
    assert team.repairer.generate_content_config.max_output_tokens == 49_152
    assert team.owner.generate_content_config.max_output_tokens == 8_192
    assert team.verifier.generate_content_config.max_output_tokens == 8_192


def test_sixsense_visual_instruction_rejects_generic_template_defaults() -> None:
    assert "inspect supplied reference images concretely" in SIXSENSE_INSTRUCTION
    assert "Do not use generic" in SIXSENSE_INSTRUCTION
    assert "explicit anti-goals" in SIXSENSE_INSTRUCTION
