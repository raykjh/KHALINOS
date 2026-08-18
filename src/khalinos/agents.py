"""Gemini 3.5 agents executed through Google ADK."""

from __future__ import annotations

import json
import os
from typing import TypeVar
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from khalinos.models import (
    AgentVerification,
    ArtifactBundle,
    QuestPlan,
    VisualConceptPlan,
    VisualSelection,
)


MODEL = os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash")
T = TypeVar("T", bound=BaseModel)


OWNER_INSTRUCTION = """
You are the KHALINOS Project Owner. Convert the approved user brief into a short,
linear sequence of outcome-bound quests. Each quest must be independently verifiable
and must shape the same browser micro-application incrementally. Use two to five quests,
never widen the supplied goal, constraints, files, budget, or acceptance criteria, and
never ask the user or a coding assistant to design later steps. The final quest must
cover every approved acceptance criterion. Return only the required schema.
""".strip()

MAKER_INSTRUCTION = """
You are the accountable KHALINOS Maker. Produce the complete current revision of one
self-contained browser micro-application for the active Quest. Return exactly five files:
index.html, styles.css, app.js, journey.json, and README.md. Use only HTML, CSS, and
vanilla JavaScript. No external URLs, packages, network calls, embedded data URLs,
eval, dynamic code loading, analytics, or placeholder TODOs. The UI must be in English,
responsive, keyboard accessible, visually coherent, and actually interactive.

journey.json must contain {"journeys":[...]} with at least one journey. Each journey has
a name and ordered steps. Supported steps are {"click":"CSS selector"},
{"press":"Keyboard key"}, and {"assert_text":"visible text"}. Selectors must point to
real controls in index.html and the journey must prove the active Quest behavior. Preserve
working behavior from the previous verified bundle and make only changes needed for the
current Quest. When the previous bundle is an approved visual foundation, preserve its
composition, typography, palette, material language, and anti-goals while adding behavior.
Keep revision_summary concise and under 500 characters. Return only the required schema.
""".strip()

VERIFIER_INSTRUCTION = """
You are the independent KHALINOS Verifier. You did not create the artifact and cannot
modify it. Judge every active Quest acceptance criterion against the supplied complete
artifact and deterministic browser evidence. PASS only when every criterion has direct
evidence. A file existing, a claim in README, or the maker's assertion is not proof of
runtime behavior. If any criterion fails, return concise repair instructions tied only to
that criterion. Never weaken criteria or approve missing evidence. Return only the schema.
""".strip()

REPAIR_INSTRUCTION = """
You are the KHALINOS Technical Repair Agent. Repair the complete artifact bundle using
the deterministic failures and independent verifier instructions. Preserve all previously
verified behavior. Do not change the Quest, criteria, authorized files, or journey format.
Keep revision_summary concise and under 500 characters. Return the complete five-file bundle
and only the required schema.
""".strip()

VISUAL_DIRECTOR_INSTRUCTION = """
You are the KHALINOS Visual Director. Read the approved brief and its bound visual
direction, then issue exactly three genuinely different but equally feasible visual concepts
for the same product. Differences must be structural: composition, hierarchy, type system,
material language, and interaction emphasis, not merely color swaps. Every concept must fit
the approved offline five-file HTML/CSS/vanilla-JavaScript profile, preserve usability, and
state concrete anti-goals that prevent generic template output. Do not widen product scope.
Return only the required schema.
""".strip()

VISUAL_MAKER_INSTRUCTION = """
You are the KHALINOS Visual Candidate Maker. Materialize one supplied visual concept as a
complete five-file browser artifact: index.html, styles.css, app.js, journey.json, and
README.md. Create a presentation-ready representative state with enough real interaction to
prove hierarchy, controls, responsive composition, and visual identity in Chromium. Follow
the concept precisely and honor all anti-goals. Use HTML, CSS, inline SVG, Canvas, and vanilla
JavaScript only. No external URL, package, network call, data URL, placeholder, or unfinished
control. journey.json may use only click, press, and assert_text steps and must produce a
meaningful screenshot. Keep revision_summary concise and under 500 characters. Return only
the required schema.
""".strip()

VISUAL_VERIFIER_INSTRUCTION = """
You are the independent KHALINOS Visual Verifier. You did not create the candidates and
cannot modify them. Compare the two or three eligible rendered Chromium screenshots against
the approved visual contract and each concept. Score contract alignment, visual hierarchy,
distinctiveness, interaction clarity, and craft/cohesion from 1 to 10. Penalize generic SaaS
templates, superficial color variation, weak typography, cramped density, unclear primary
action, or divergence from explicit anti-goals. Judge visible evidence rather than README or
maker claims. Assess only candidates identified as eligible and shown in screenshots, ordered
by candidate ID. Select the candidate with the highest rubric average; ties may be resolved
by stronger contract alignment, then distinctiveness. Return only the required schema.
""".strip()


def _agent(
    name: str,
    instruction: str,
    schema: type[T],
    *,
    temperature: float,
    max_output_tokens: int = 8192,
) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=MODEL,
        instruction=instruction,
        output_schema=schema,
        output_key=f"{name}_output",
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )


class AgentTeam:
    """Seven role-separated ADK agents; Python only enforces the approved state machine."""

    def __init__(self) -> None:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        self.owner = _agent("khalinos_project_owner", OWNER_INSTRUCTION, QuestPlan, temperature=0.1)
        self.maker = _agent(
            "khalinos_accountable_maker",
            MAKER_INSTRUCTION,
            ArtifactBundle,
            temperature=0.25,
            max_output_tokens=49_152,
        )
        self.verifier = _agent("khalinos_independent_verifier", VERIFIER_INSTRUCTION, AgentVerification, temperature=0.0)
        self.repairer = _agent(
            "khalinos_technical_repair",
            REPAIR_INSTRUCTION,
            ArtifactBundle,
            temperature=0.1,
            max_output_tokens=49_152,
        )
        self.visual_director = _agent(
            "khalinos_visual_director",
            VISUAL_DIRECTOR_INSTRUCTION,
            VisualConceptPlan,
            temperature=0.35,
        )
        self.visual_maker = _agent(
            "khalinos_visual_candidate_maker",
            VISUAL_MAKER_INSTRUCTION,
            ArtifactBundle,
            temperature=0.4,
            max_output_tokens=49_152,
        )
        self.visual_verifier = _agent(
            "khalinos_visual_verifier",
            VISUAL_VERIFIER_INSTRUCTION,
            VisualSelection,
            temperature=0.0,
        )
        self.call_count = 0

    async def _run(
        self,
        agent: LlmAgent,
        payload: dict,
        schema: type[T],
        *,
        extra_parts: list[types.Part] | None = None,
    ) -> T:
        session_service = InMemorySessionService()
        session_id = uuid4().hex
        user_id = "khalinos-worker"
        app_name = "khalinos-autonomous-execution"
        await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
        parts = [types.Part(text=json.dumps(payload, ensure_ascii=False, indent=2))]
        parts.extend(extra_parts or [])
        message = types.Content(role="user", parts=parts)
        final_text = ""
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(part.text or "" for part in event.content.parts)
        self.call_count += 1
        if not final_text:
            raise RuntimeError(f"{agent.name} returned no structured response")
        return schema.model_validate(json.loads(final_text))

    async def plan(self, payload: dict) -> QuestPlan:
        return await self._run(self.owner, payload, QuestPlan)

    async def make(self, payload: dict) -> ArtifactBundle:
        return await self._run(self.maker, payload, ArtifactBundle)

    async def verify(self, payload: dict) -> AgentVerification:
        return await self._run(self.verifier, payload, AgentVerification)

    async def repair(self, payload: dict) -> ArtifactBundle:
        return await self._run(self.repairer, payload, ArtifactBundle)

    async def plan_visuals(self, payload: dict) -> VisualConceptPlan:
        return await self._run(self.visual_director, payload, VisualConceptPlan)

    async def make_visual(self, payload: dict) -> ArtifactBundle:
        return await self._run(self.visual_maker, payload, ArtifactBundle)

    async def select_visual(self, payload: dict, screenshots: list[tuple[str, bytes]]) -> VisualSelection:
        parts: list[types.Part] = []
        for candidate_id, data in screenshots:
            parts.append(types.Part.from_text(text=f"Rendered Chromium screenshot for {candidate_id}"))
            parts.append(types.Part.from_bytes(data=data, mime_type="image/png"))
        return await self._run(
            self.visual_verifier,
            payload,
            VisualSelection,
            extra_parts=parts,
        )
