from __future__ import annotations

import pytest

from khalinos.models import RouteCandidateAssessment, RouteRecommendation, RouteRecommendationRequest
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.routing import enforce_required_route, validate_route_recommendation


def candidates():
    return APPROVED_TOOLPACKS.routing_candidates(work_mode="new_product_build")


def assessment(toolpack_id: str, fit: str) -> RouteCandidateAssessment:
    return RouteCandidateAssessment(
        toolpack_id=toolpack_id,
        fit=fit,
        reason="This route has a clearly bounded relationship to the requested outcome.",
        expected_result="A bounded result that stays inside the approved ToolPack contract.",
        limitations=[],
    )


def test_route_validation_accepts_only_approved_candidates_and_prefers_exact() -> None:
    route = RouteRecommendation(
        status="recommended",
        recommended_toolpack_id="browser.product",
        candidates=[
            assessment("browser.product", "exact"),
            assessment("godot.gameplay", "bounded_alternative"),
            assessment("godot.topology", "bounded_alternative"),
            assessment("godot.visual-prototype", "bounded_alternative"),
        ],
    )
    assert validate_route_recommendation(route, candidates()) == route


def test_route_validation_rejects_invented_or_omitted_toolpacks() -> None:
    route = RouteRecommendation(
        status="recommended",
        recommended_toolpack_id="browser.product",
        candidates=[assessment("browser.product", "exact")],
    )
    with pytest.raises(ValueError, match="every approved candidate"):
        validate_route_recommendation(route, candidates())


def test_route_validation_cannot_prefer_bounded_over_exact() -> None:
    route = RouteRecommendation(
        status="recommended",
        recommended_toolpack_id="godot.topology",
        candidates=[
            assessment("browser.product", "exact"),
            assessment("godot.gameplay", "bounded_alternative"),
            assessment("godot.topology", "bounded_alternative"),
            assessment("godot.visual-prototype", "bounded_alternative"),
        ],
    )
    with pytest.raises(ValueError, match="prefer an exact"):
        validate_route_recommendation(route, candidates())


def test_route_validation_allows_truthful_unsupported_result() -> None:
    route = RouteRecommendation(
        status="unsupported",
        candidates=[
            assessment("browser.product", "incompatible"),
            assessment("godot.gameplay", "incompatible"),
            assessment("godot.topology", "incompatible"),
            assessment("godot.visual-prototype", "incompatible"),
        ],
    )
    assert validate_route_recommendation(route, candidates()) == route


def test_explicit_playable_godot_goal_cannot_be_routed_to_topology() -> None:
    route = RouteRecommendation(
        status="recommended",
        recommended_toolpack_id="godot.topology",
        candidates=[
            assessment("browser.product", "incompatible"),
            assessment("godot.gameplay", "bounded_alternative"),
            assessment("godot.topology", "exact"),
            assessment("godot.visual-prototype", "bounded_alternative"),
        ],
    )
    request = RouteRecommendationRequest(
        project_name="Trinity Survivors",
        goal=(
            "Create a playable 2D top-down survival roguelike game in Godot with "
            "automatic attacks, enemies, shared health, skills, and level choices."
        ),
    )

    corrected = enforce_required_route(route, candidates(), request)

    assert corrected.recommended_toolpack_id == "godot.gameplay"
    assert next(
        item.fit for item in corrected.candidates if item.toolpack_id == "godot.topology"
    ) == "bounded_alternative"
    assert validate_route_recommendation(corrected, candidates()) == corrected


def test_non_gameplay_godot_goal_keeps_the_model_recommendation() -> None:
    route = RouteRecommendation(
        status="recommended",
        recommended_toolpack_id="godot.topology",
        candidates=[
            assessment("browser.product", "bounded_alternative"),
            assessment("godot.gameplay", "bounded_alternative"),
            assessment("godot.topology", "exact"),
            assessment("godot.visual-prototype", "bounded_alternative"),
        ],
    )
    request = RouteRecommendationRequest(
        project_name="Godot Screen Map",
        goal="Create a Godot screen and overlay navigation topology with no gameplay mechanics.",
    )

    assert enforce_required_route(route, candidates(), request) == route
