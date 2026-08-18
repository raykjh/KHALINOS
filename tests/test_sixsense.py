from __future__ import annotations

import base64

import pytest

from khalinos.intake import answer_intake, authorized_brief, restart_intake, start_intake
from khalinos.intake_storage import LocalIntakeStore
from khalinos.models import (
    ALL_SENSE_DIMENSIONS,
    ExecutionEstimate,
    IntakeAnswer,
    IntakeCreate,
    IntakeRevision,
    OutcomePreview,
    SenseDecision,
    SenseDimension,
    SenseQuestion,
    SourceUpload,
    UserBrief,
)
from khalinos.sixsense import validate_decision


def preview() -> OutcomePreview:
    return OutcomePreview(
        final_result="A polished, bounded browser decision product with a complete primary workflow.",
        required_enablers=["A modern browser with local storage."],
        exclusions_and_preservation=["No external network dependency."],
        visual_direction="A calm editorial interface with clear hierarchy and a distinctive warm accent.",
        operating_context=["Desktop and narrow mobile browser use."],
        completion_and_quality=["The primary journey passes in Chromium.", "The final screenshot meets the approved direction."],
        authority_budget_and_delivery=["Autonomous execution is bounded to four Quests and two repairs per Quest."],
        estimate=ExecutionEstimate(
            quest_count=3,
            cost_usd_min=0.2,
            cost_usd_max=1.5,
            duration_minutes_min=3,
            duration_minutes_max=15,
        ),
        recommended_brief=UserBrief(
            project_name="Decision product",
            goal="Create a polished browser decision product with one complete user journey.",
            constraints=["No external network calls."],
            acceptance_criteria=["The primary journey works.", "The approved visual direction is visible."],
        ),
    )


class AdaptiveFake:
    def __init__(self) -> None:
        self.calls = 0
        self.source_counts: list[int] = []

    async def assess(self, record, source_payloads):
        self.calls += 1
        self.source_counts.append(len(source_payloads))
        if SenseDimension.EXPERIENCE_VISUAL_DIRECTION.value not in record.answers:
            return SenseDecision(
                status="question",
                resolved_dimensions=[
                    SenseDimension.REQUIRED_ENABLERS,
                    SenseDimension.EXCLUSIONS_PRESERVATION,
                    SenseDimension.OPERATING_CONTEXT,
                    SenseDimension.COMPLETION_QUALITY_STANDARD,
                    SenseDimension.AUTHORITY_BUDGET_DELIVERY,
                ],
                next_question=SenseQuestion(
                    dimension=SenseDimension.EXPERIENCE_VISUAL_DIRECTION,
                    question="Which visual direction should distinguish the finished product from a generic template?",
                    recommended_answer="Use an editorial layout, warm brass accents, restrained motion, and strong hierarchy.",
                    why_it_matters="Visual direction materially changes layout, styling, and the evidence used for approval.",
                ),
            )
        return SenseDecision(
            status="ready",
            resolved_dimensions=ALL_SENSE_DIMENSIONS,
            preview=preview(),
        )


async def test_adaptive_flow_asks_only_missing_dimension_and_preserves_source(tmp_path) -> None:
    store = LocalIntakeStore(tmp_path)
    agent = AdaptiveFake()
    request = IntakeCreate(
        project_name="Decision product",
        goal="Create a complete team decision product with a polished and responsive interface.",
        sources=[SourceUpload(
            filename="reference.md",
            media_type="text/markdown",
            data_base64=base64.b64encode(b"# Visual reference").decode(),
        )],
    )
    record = await start_intake(request, store=store, agent=agent)
    assert record.status == "sensing"
    assert record.current_question.dimension == SenseDimension.EXPERIENCE_VISUAL_DIRECTION

    record = await answer_intake(
        record.intake_id,
        IntakeAnswer(
            dimension=SenseDimension.EXPERIENCE_VISUAL_DIRECTION,
            answer=record.current_question.recommended_answer,
        ),
        store=store,
        agent=agent,
    )
    assert record.status == "ready"
    assert set(record.resolved_dimensions) == set(ALL_SENSE_DIMENSIONS)
    assert agent.source_counts == [1, 1]


async def test_revision_keeps_sources_and_restarts_discovery(tmp_path) -> None:
    store = LocalIntakeStore(tmp_path)
    agent = AdaptiveFake()
    request = IntakeCreate(
        project_name="Decision product",
        goal="Create a complete team decision product with a polished and responsive interface.",
        sources=[SourceUpload(filename="facts.txt", media_type="text/plain", data_base64=base64.b64encode(b"facts").decode())],
    )
    first = await start_intake(request, store=store, agent=agent)
    first = await answer_intake(
        first.intake_id,
        IntakeAnswer(dimension=first.current_question.dimension, answer=first.current_question.recommended_answer),
        store=store,
        agent=agent,
    )
    revised = await restart_intake(
        first.intake_id,
        IntakeRevision(change_request="Make the visual language feel more tactile and less corporate."),
        store=store,
        agent=agent,
    )
    assert revised.intake_id != first.intake_id
    assert revised.sources == first.sources
    assert "Requested revision" in revised.goal
    assert store.source_bytes(revised.intake_id, revised.sources[0]) == b"facts"


def test_sixsense_cannot_repeat_a_resolved_dimension() -> None:
    record = __import__("khalinos.models", fromlist=["IntakeRecord"]).IntakeRecord(
        intake_id="a" * 32,
        project_name="Demo",
        goal="Create a sufficiently detailed browser product for a complete user workflow.",
        resolved_dimensions=[SenseDimension.REQUIRED_ENABLERS],
    )
    decision = SenseDecision(
        status="question",
        resolved_dimensions=[SenseDimension.REQUIRED_ENABLERS],
        next_question=SenseQuestion(
            dimension=SenseDimension.REQUIRED_ENABLERS,
            question="Which required external capability should the product use for its primary workflow?",
            recommended_answer="Use only capabilities already available in the approved browser runtime.",
            why_it_matters="The dependency changes feasibility and execution authority.",
        ),
    )
    with pytest.raises(ValueError, match="repeated"):
        validate_decision(record, decision)


def test_authorization_binds_visual_direction_and_quality_to_execution_brief() -> None:
    outcome = preview()
    brief = authorized_brief(outcome)
    assert any(item.startswith("Approved visual direction:") for item in brief.constraints)
    assert set(outcome.completion_and_quality).issubset(set(brief.acceptance_criteria))
    assert brief.max_quests == outcome.estimate.quest_count
    assert brief.goal == outcome.final_result


async def test_rejects_source_path_traversal(tmp_path) -> None:
    request = IntakeCreate(
        project_name="Decision product",
        goal="Create a complete team decision product with a polished and responsive interface.",
        sources=[SourceUpload(filename="../secret.txt", media_type="text/plain", data_base64=base64.b64encode(b"x").decode())],
    )
    with pytest.raises(ValueError, match="filename"):
        await start_intake(request, store=LocalIntakeStore(tmp_path), agent=AdaptiveFake())
