from __future__ import annotations

import pytest

from khalinos.models import (
    ArtifactBundle,
    ArtifactFile,
    QuestPlan,
    QuestSpec,
    UserBrief,
    VisualAssessment,
    VisualSelection,
)


def brief() -> UserBrief:
    return UserBrief(
        project_name="Test product",
        goal="Create a small interactive product that demonstrates one complete user workflow.",
        acceptance_criteria=["The primary action works.", "The interface is responsive."],
    )


def test_brief_has_fixed_safe_output_surface() -> None:
    assert len(brief().authorized_output_files) == 5
    with pytest.raises(ValueError):
        brief().model_copy(update={"authorized_output_files": ["unsafe.py"]}).model_validate(
            {**brief().model_dump(), "authorized_output_files": ["unsafe.py"]}
        )


def test_quest_plan_requires_linear_receipt_chain() -> None:
    plan = QuestPlan(
        product_summary="A complete bounded browser product for one user workflow.",
        architecture_decision="Use a self-contained accessible browser application with local state.",
        quests=[
            QuestSpec(quest_id="Q1", objective="Create the runnable product shell and first interaction.", acceptance_criteria=["It starts."], evidence_required=["Browser screenshot."]),
            QuestSpec(quest_id="Q2", objective="Complete and verify the approved product behavior.", acceptance_criteria=["It works."], evidence_required=["Runtime journey."], depends_on=["Q1"]),
        ],
    )
    assert len(plan.quests) == 2


def test_artifact_requires_exact_file_set() -> None:
    files = [ArtifactFile(path=name, content="x") for name in ["index.html", "styles.css", "app.js", "journey.json", "README.md"]]
    assert len(ArtifactBundle(revision_summary="Complete safe revision", files=files).files) == 5


def visual_assessment(candidate_id: str, score: int) -> VisualAssessment:
    return VisualAssessment(
        candidate_id=candidate_id,
        contract_alignment=score,
        visual_hierarchy=score,
        distinctiveness=score,
        interaction_clarity=score,
        craft_and_cohesion=score,
        strengths=["Clear visual hierarchy."],
    )


def test_visual_selection_requires_an_assessed_top_scoring_candidate() -> None:
    assessments = [visual_assessment("V1", 8), visual_assessment("V2", 9)]
    with pytest.raises(ValueError, match="highest rubric score"):
        VisualSelection(
            assessments=assessments,
            selected_candidate_id="V1",
            rationale="V1 was selected even though its rubric score is lower than V2.",
        )
    with pytest.raises(ValueError, match="must be assessed"):
        VisualSelection(
            assessments=assessments,
            selected_candidate_id="V3",
            rationale="V3 was selected without a corresponding eligible visual assessment.",
        )
