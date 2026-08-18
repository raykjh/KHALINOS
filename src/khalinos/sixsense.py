"""Adaptive six-dimension outcome discovery powered by Gemini and Google ADK."""

from __future__ import annotations

import json
import os
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from khalinos.models import ALL_SENSE_DIMENSIONS, IntakeRecord, SenseDecision, SenseDimension


SIXSENSE_INSTRUCTION = """
You are KHALINOS SixSense, an adaptive project discovery agent. Your job is to turn a
non-expert user's goal and supplied sources into an executable, bounded outcome contract.
The intake includes a static material inspection performed before the goal was submitted.
Use its recommended work mode as advisory evidence, not as execution authority. For existing
projects, distinguish source-backed work, reproduce-and-repair, and executable-only black-box
diagnosis. Never promise a repair from an executable alone, and preserve existing behavior or
files unless the goal explicitly authorizes changing them.
Internally inspect exactly these six dimensions:

1. required_enablers: required data, APIs, accounts, engines, assets, expertise, or inputs;
2. exclusions_preservation: forbidden scope, non-goals, and existing elements to preserve;
3. experience_visual_direction: desired experience, visual hierarchy, art direction,
   references, and visual anti-goals;
4. operating_context: users, devices, runtime, integrations, persistence, accessibility,
   performance, and online/offline conditions;
5. completion_quality_standard: observable completion, evidence, risk level, and the
   appropriate strictness for this project type;
6. authority_budget_delivery: autonomy, approval boundaries, money, time, and deliverables.

Do not treat these as six mandatory survey questions. Infer a dimension when the goal,
sources, previous answers, authoritative defaults, and low-risk assumptions make it clear.
Ask only when a missing choice could materially change the result, cost, authority, safety,
or visual direction. Ask exactly one concrete question at a time and no more than three
questions across one intake. Never repeat a dimension that is already answered or resolved.

Every question must request a decision that the user can reasonably own: a subjective
preference, a preservation boundary, an authority choice, or a behavior for which multiple
alternatives are equally professionally valid. Do not ask the user to choose technical
implementation details or established best practices that KHALINOS can decide safely.
Provide two to four mutually exclusive answer_options of one to five words and no more than
48 characters each, such as "Classic", "Modern", or "No preference". The UI supplies an additional Other field.
Do not provide or preselect a recommended answer. Never put a plan, feature bundle,
rationale, or acceptance criteria inside an option. Explain why the choice matters in one
short sentence. The options must expose a real choice rather than different phrasings of
the same recommendation. Do not ask whether to use first-click safety, accessibility,
responsive layout, correct error handling, or another clearly better standard; apply it.

A confirmed answer binds the user's actual preference, not a long implementation bundle.
KHALINOS remains responsible for choosing established professional defaults and may add
standard or clearly improved behavior that makes the requested product more complete,
reliable, accessible, or usable within the approved budget. Do not ask the user to approve a
choice when one option is plainly the current professional standard. If the user states no
preference, choose the strongest suitable standard rather than removing useful functionality.
Keep subjective preferences distinct from those autonomous quality decisions, and describe
the resulting professional defaults transparently in the Outcome Preview.

When every dimension is sufficiently resolved, return a realistic Outcome Preview and a
recommended fixed five-file browser-product brief. Translate discoveries into observable
acceptance criteria; never claim an unavailable dependency exists. Cost and duration are
bounded estimates for the autonomous run, not guarantees. Never expand authority beyond
what the user supplied. Return only the required schema.

The currently approved execution profile is deliberately narrow: exactly index.html,
styles.css, app.js, journey.json, and README.md; HTML, CSS, inline SVG, Canvas, and vanilla
JavaScript only; no CDN, external URL, package, network call, generated binary asset, data
URL, server-side product dependency, or extra output file. It supports polished interactive
browser micro-apps, not a production 3D engine project. Every recommendation must be
feasible inside this profile. If the requested outcome materially needs a capability outside
it, ask under required_enablers whether to choose an in-profile prototype or seek separate
authorization for a future capability. Never recommend a forbidden dependency as a default.
The current browser micro-app Cloud worker has a 30-minute per-execution safety slice and a
$5 maximum run budget. The 30 minutes is not a user-project deadline; it bounds one runaway
execution. This current profile is not yet resumable, so its approved outcome must fit one
slice. Prefer the strongest complete, polished outcome that fits the slice. Include
recognizable standard modes, presets, and quality features when they make the requested
product materially better and remain feasible; choose them autonomously rather than turning
them into user questions. Avoid unrelated novelty and never trade away visual finish or
reliability merely to increase feature count. Every authorized run includes a three-candidate visual competition before
the Quest chain, adding five Gemini calls. Estimates must include that stage, stay inside the
hard safety limits, and remain realistic rather than simply equal to the maximum.

For experience_visual_direction, inspect supplied reference images concretely: composition,
hierarchy, density, typography, palette, material cues, interaction emphasis, strengths to
preserve, and weaknesses to change. A redesign question and recommendation must mention
observed qualities or the product's specific purpose. Do not use generic "SaaS dashboard",
glassmorphism, neon gradient, glowing-card, or trendy-template language as a recommended
default unless the user explicitly asks for it. Recommend one distinctive, feasible art
direction with explicit anti-goals, not a menu of fashionable styles.
""".strip()


class SixSenseAgent:
    def __init__(self) -> None:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        model = os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash")
        self.agent = LlmAgent(
            name="khalinos_sixsense",
            model=model,
            instruction=SIXSENSE_INSTRUCTION,
            output_schema=SenseDecision,
            output_key="khalinos_sixsense_output",
            include_contents="none",
            generate_content_config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )

    async def assess(self, record: IntakeRecord, source_payloads: list[tuple[str, str, bytes]]) -> SenseDecision:
        session_service = InMemorySessionService()
        session_id = uuid4().hex
        user_id = "khalinos-intake"
        app_name = "khalinos-sixsense"
        await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        runner = Runner(agent=self.agent, app_name=app_name, session_service=session_service)
        payload = {
            "project_name": record.project_name,
            "goal": record.goal,
            "project_locator": record.project_locator,
            "material_inspection": record.material_inspection.model_dump(mode="json") if record.material_inspection else None,
            "sources": [
                {"filename": name, "media_type": media_type, "size_bytes": len(data)}
                for name, media_type, data in source_payloads
            ],
            "confirmed_answers": record.answers,
            "already_resolved_dimensions": [item.value for item in record.resolved_dimensions],
            "allowed_dimensions": [item.value for item in ALL_SENSE_DIMENSIONS],
            "approved_execution_profile": {
                "files": ["index.html", "styles.css", "app.js", "journey.json", "README.md"],
                "technologies": ["HTML", "CSS", "inline SVG", "Canvas", "vanilla JavaScript"],
                "forbidden": ["CDN", "external URL", "package", "network call", "binary asset", "data URL", "server dependency"],
                "quest_limit": "2 to 5",
                "repair_limit_per_quest": "0 to 2",
                "maximum_run_budget_usd": 5,
                "maximum_duration_minutes": 30,
                "scope_rule": "prefer the smallest complete polished outcome",
                "visual_competition": "three candidates, rendered screenshots, independent multimodal selection",
            },
        }
        parts = [types.Part.from_text(text=json.dumps(payload, ensure_ascii=False, indent=2))]
        for name, media_type, data in source_payloads:
            if media_type.startswith("image/"):
                parts.append(types.Part.from_text(text=f"User source image: {name}"))
                parts.append(types.Part.from_bytes(data=data, mime_type=media_type))
            else:
                text = data.decode("utf-8", errors="replace")[:40_000]
                parts.append(types.Part.from_text(text=f"User source text: {name}\n{text}"))
        final_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=parts),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(part.text or "" for part in event.content.parts)
        if not final_text:
            raise RuntimeError("SixSense returned no structured response")
        decision = SenseDecision.model_validate(json.loads(final_text))
        validate_decision(record, decision)
        return decision


def validate_decision(record: IntakeRecord, decision: SenseDecision) -> None:
    answered = {SenseDimension(key) for key in record.answers}
    previously_resolved = set(record.resolved_dimensions)
    resolved = set(decision.resolved_dimensions)
    if not previously_resolved.issubset(resolved):
        raise ValueError("SixSense cannot reopen a resolved dimension during one intake")
    if not answered.issubset(resolved):
        raise ValueError("SixSense must preserve every confirmed answer as resolved")
    if decision.next_question:
        if len(record.answers) >= 3:
            raise ValueError("SixSense cannot ask more than three user questions")
        dimension = decision.next_question.dimension
        if dimension in answered or dimension in resolved:
            raise ValueError("SixSense repeated an answered or resolved dimension")
