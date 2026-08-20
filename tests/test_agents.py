from __future__ import annotations

import json

from khalinos.agents import (
    AgentTeam,
    VISUAL_MAKER_INSTRUCTION,
    compact_vertex_json_schema,
    normalize_structured_result,
)
from khalinos.godot_gameplay import GodotGameplayPlan
from khalinos.godot_topology import GodotRegion, GodotTopologyPlan
from khalinos.models import QuestPlan, QuestSpec
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
    assert team.visual_asset_verifier.generate_content_config.max_output_tokens == 8_192
    assert team.godot_quest_owner.generate_content_config.max_output_tokens == 8_192
    assert team.godot_topology_owner.generate_content_config.max_output_tokens == 8_192


def test_godot_planners_use_vertex_safe_json_schemas() -> None:
    team = AgentTeam()
    assert team.godot_quest_owner.output_schema is None
    assert team.godot_gameplay_owner.output_schema is None
    assert team.godot_quest_owner.generate_content_config.response_json_schema
    gameplay_schema = team.godot_gameplay_owner.generate_content_config.response_json_schema
    assert gameplay_schema == compact_vertex_json_schema(GodotGameplayPlan)
    assert len(json.dumps(gameplay_schema)) < 3_500
    assert "pattern" not in json.dumps(gameplay_schema)


def test_trusted_normalization_repairs_only_structural_model_variance() -> None:
    quest_payload = {
        "product_summary": "s" * 900,
        "architecture_decision": "a" * 900,
        "quests": [
            {"quest_id": "long_name", "depends_on": ["wrong"]},
            {"quest_id": "another_name", "depends_on": []},
        ],
    }
    normalized_quests = normalize_structured_result(QuestPlan, quest_payload)
    assert len(normalized_quests["product_summary"]) == 800
    assert normalized_quests["quests"][0]["quest_id"] == "Q1"
    assert normalized_quests["quests"][1]["depends_on"] == ["Q1"]

    gameplay_payload = {
        "upgrade_role_order": ["tank", "damage", "support", "tank"],
        "heroes": [{"color_hex": "#A1B2C3"}],
        "enemies": [{"color_hex": "112233"}],
    }
    normalized_gameplay = normalize_structured_result(GodotGameplayPlan, gameplay_payload)
    assert normalized_gameplay["upgrade_role_order"] == ["tank", "damage", "support"]
    assert normalized_gameplay["heroes"][0]["color_hex"] == "A1B2C3"


def test_sixsense_visual_instruction_rejects_generic_template_defaults() -> None:
    assert "inspect supplied reference images concretely" in SIXSENSE_INSTRUCTION
    assert "Do not use generic" in SIXSENSE_INSTRUCTION
    assert "explicit anti-goals" in SIXSENSE_INSTRUCTION


def test_sixsense_questions_preserve_real_user_choice_and_professional_defaults() -> None:
    assert "two to four mutually exclusive answer_options" in SIXSENSE_INSTRUCTION
    assert "no more than\n48 characters each" in SIXSENSE_INSTRUCTION
    assert "no more than six" in SIXSENSE_INSTRUCTION
    assert "established best practices" in SIXSENSE_INSTRUCTION
    assert "first-click safety" in SIXSENSE_INSTRUCTION
    assert "strongest suitable standard" in SIXSENSE_INSTRUCTION
    assert "standard modes, presets, and quality features" in SIXSENSE_INSTRUCTION


def test_visual_maker_has_exact_runtime_and_accessibility_contract() -> None:
    assert '{"journeys":[...]}' in VISUAL_MAKER_INSTRUCTION
    assert '{"click":"CSS selector"}' in VISUAL_MAKER_INSTRUCTION
    assert "Do not use type, selector, text, or key fields" in VISUAL_MAKER_INSTRUCTION
    assert "explicit label or aria-label" in VISUAL_MAKER_INSTRUCTION


async def test_godot_owner_uses_two_bounded_schemas_then_host_combines_them(monkeypatch) -> None:
    team = AgentTeam()
    calls: list[tuple[str, type]] = []

    async def fake_run(agent, payload, schema, **kwargs):
        del kwargs
        calls.append((agent.name, schema))
        if schema is QuestPlan:
            return QuestPlan(
                product_summary="A bounded Godot topology for the approved offline product outcome.",
                architecture_decision="Use the trusted topology compiler and digest-bound headless verifier.",
                quests=[
                    QuestSpec(
                        quest_id="Q1",
                        objective="Create the bounded approved arrival topology without widening scope.",
                        acceptance_criteria=["The arrival screen opens."],
                        evidence_required=["Godot headless receipt."],
                    ),
                    QuestSpec(
                        quest_id="Q2",
                        objective="Verify all declared regions through the approved headless runtime.",
                        acceptance_criteria=["Every region loads."],
                        evidence_required=["Godot headless receipt."],
                        depends_on=["Q1"],
                    ),
                ],
            )
        assert payload["approved_quest_plan"]["quests"][0]["quest_id"] == "Q1"
        return GodotTopologyPlan(
            project_name="Route Observatory",
            initial_region="arrival",
            regions=(
                GodotRegion(region_id="arrival", label="Arrival", transitions=("result",)),
                GodotRegion(region_id="result", label="Result"),
            ),
        )

    monkeypatch.setattr(team, "_run", fake_run)
    result = await team.plan_godot({"approved_brief": {"project_name": "Route Observatory"}})

    assert [schema for _name, schema in calls] == [QuestPlan, GodotTopologyPlan]
    assert result.quest_plan.quests[1].depends_on == ["Q1"]
    assert result.topology.project_name == "Route Observatory"
