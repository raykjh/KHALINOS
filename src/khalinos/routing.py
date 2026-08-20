"""Bounded semantic routing across statically approved ToolPacks."""

from __future__ import annotations

import json
import os
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from khalinos.models import MaterialInspection, RouteRecommendation, RouteRecommendationRequest
from khalinos.toolpacks import ToolPackManifest


ROUTE_INSTRUCTION = """
You are the KHALINOS Route Advisor. Compare one user's requested outcome only with the
approved ToolPack candidates supplied in the payload. You may not invent a ToolPack,
runtime, capability, file, or exception.

For every candidate return exactly one assessment:
- exact: the complete requested outcome is feasible inside the declared scope;
- bounded_alternative: a useful result is possible only after a clear scope reduction;
- incompatible: the candidate cannot honestly deliver the requested outcome.

Prefer an exact route over every bounded alternative. Recommend the strongest exact fit.
If no exact fit exists, recommend a bounded alternative only when expected_result states
the reduced outcome plainly. If every candidate is incompatible, return unsupported.
Do not mistake a named engine for capability: a Godot topology ToolPack proves connected
screens and overlays, not gameplay. A playable browser product should use the browser route
when its full behavior is feasible there. Return only RouteRecommendation.
""".strip()


_GODOT_GAMEPLAY_SIGNALS = (
    "playable",
    "gameplay",
    "survival",
    "roguelike",
    "combat",
    "attack",
    "enemy",
    "enemies",
    "health",
    "level",
    "skill",
    "ability",
    "victory",
    "defeat",
)
_NON_GAMEPLAY_GODOT_ROUTES = {
    "godot.topology",
    "godot.visual-prototype",
}


def requires_godot_gameplay(request: RouteRecommendationRequest) -> bool:
    """Recognize an explicit playable Godot outcome without asking a model to grant scope."""

    text = f"{request.project_name}\n{request.goal}".lower()
    if "godot" not in text:
        return False
    matched = sum(signal in text for signal in _GODOT_GAMEPLAY_SIGNALS)
    return ("playable" in text or "gameplay" in text) and matched >= 3


def enforce_required_route(
    recommendation: RouteRecommendation,
    candidates: tuple[ToolPackManifest, ...],
    request: RouteRecommendationRequest,
) -> RouteRecommendation:
    """Prevent a narrower prototype route from replacing required playable mechanics."""

    if not requires_godot_gameplay(request):
        return recommendation
    approved_ids = {item.toolpack_id for item in candidates}
    if "godot.gameplay" not in approved_ids:
        return recommendation
    by_id = {item.toolpack_id: item for item in recommendation.candidates}
    gameplay = by_id.get("godot.gameplay")
    if gameplay is None or gameplay.fit == "incompatible":
        raise ValueError(
            "the approved Godot Gameplay route must remain usable for an explicit playable Godot goal"
        )
    corrected = [
        item.model_copy(update={"fit": "bounded_alternative"})
        if item.toolpack_id != "godot.gameplay" and item.fit == "exact"
        else item
        for item in recommendation.candidates
    ]
    return recommendation.model_copy(update={
        "status": "recommended",
        "recommended_toolpack_id": "godot.gameplay",
        "candidates": corrected,
    })


class RouteAdvisor:
    def __init__(self) -> None:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        self.agent = LlmAgent(
            name="khalinos_route_advisor",
            model=os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash"),
            instruction=ROUTE_INSTRUCTION,
            output_schema=RouteRecommendation,
            output_key="khalinos_route_recommendation",
            include_contents="none",
            generate_content_config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )

    async def recommend(
        self,
        request: RouteRecommendationRequest,
        inspection: MaterialInspection,
        candidates: tuple[ToolPackManifest, ...],
    ) -> RouteRecommendation:
        payload = {
            "project_name": request.project_name,
            "goal": request.goal,
            "material_inspection": inspection.model_dump(mode="json"),
            "approved_candidates": [
                {
                    "toolpack_id": item.toolpack_id,
                    "display_name": item.display_name,
                    "description": item.description,
                    "version": item.version,
                    "primary_project_kind": item.routing.primary_project_kind,
                    "supported_outcomes": item.routing.supported_outcomes,
                    "excluded_outcomes": item.routing.excluded_outcomes,
                    "selection_guidance": item.routing.selection_guidance,
                    "evidence_types": item.evidence.evidence_types,
                    "authorized_output": item.output.artifact_kind,
                }
                for item in candidates
            ],
        }
        session_service = InMemorySessionService()
        session_id = uuid4().hex
        await session_service.create_session(
            app_name=self.agent.name, user_id="khalinos-route", session_id=session_id
        )
        runner = Runner(agent=self.agent, app_name=self.agent.name, session_service=session_service)
        final_text = ""
        async for event in runner.run_async(
            user_id="khalinos-route",
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=json.dumps(payload, ensure_ascii=False, indent=2))],
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(part.text or "" for part in event.content.parts)
        if not final_text:
            raise RuntimeError("Route Advisor returned no structured response")
        recommendation = enforce_required_route(
            RouteRecommendation.model_validate_json(final_text), candidates, request
        )
        return validate_route_recommendation(recommendation, candidates)


def validate_route_recommendation(
    recommendation: RouteRecommendation,
    candidates: tuple[ToolPackManifest, ...],
) -> RouteRecommendation:
    approved_ids = {item.toolpack_id for item in candidates}
    returned_ids = {item.toolpack_id for item in recommendation.candidates}
    if returned_ids != approved_ids:
        raise ValueError("Route Advisor must assess every approved candidate and no others")
    exact = [item for item in recommendation.candidates if item.fit == "exact"]
    if exact and recommendation.status != "recommended":
        raise ValueError("Route Advisor cannot reject an exact approved route")
    if exact and recommendation.recommended_toolpack_id not in {item.toolpack_id for item in exact}:
        raise ValueError("Route Advisor must prefer an exact route over a bounded alternative")
    usable = [item for item in recommendation.candidates if item.fit != "incompatible"]
    if recommendation.status == "unsupported" and usable:
        raise ValueError("Route Advisor cannot reject a usable bounded route")
    if recommendation.status == "recommended" and not usable:
        raise ValueError("Route Advisor cannot recommend when every route is incompatible")
    return recommendation
