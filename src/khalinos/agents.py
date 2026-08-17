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

from khalinos.models import AgentVerification, ArtifactBundle, QuestPlan


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
current Quest. Return only the required schema.
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
Return the complete five-file bundle and only the required schema.
""".strip()


def _agent(name: str, instruction: str, schema: type[T], *, temperature: float) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=MODEL,
        instruction=instruction,
        output_schema=schema,
        output_key=f"{name}_output",
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )


class AgentTeam:
    """Four role-separated ADK agents; Python only enforces the approved state machine."""

    def __init__(self) -> None:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        self.owner = _agent("khalinos_project_owner", OWNER_INSTRUCTION, QuestPlan, temperature=0.1)
        self.maker = _agent("khalinos_accountable_maker", MAKER_INSTRUCTION, ArtifactBundle, temperature=0.25)
        self.verifier = _agent("khalinos_independent_verifier", VERIFIER_INSTRUCTION, AgentVerification, temperature=0.0)
        self.repairer = _agent("khalinos_technical_repair", REPAIR_INSTRUCTION, ArtifactBundle, temperature=0.1)
        self.call_count = 0

    async def _run(self, agent: LlmAgent, payload: dict, schema: type[T]) -> T:
        session_service = InMemorySessionService()
        session_id = uuid4().hex
        user_id = "khalinos-worker"
        app_name = "khalinos-autonomous-execution"
        await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
        message = types.Content(
            role="user",
            parts=[types.Part(text=json.dumps(payload, ensure_ascii=False, indent=2))],
        )
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

