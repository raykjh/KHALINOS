"""Adaptive six-dimension outcome discovery powered by Gemini and Google ADK."""

from __future__ import annotations

import json
import os
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from khalinos.models import (
    ALL_SENSE_DIMENSIONS,
    IntakeRecord,
    OutcomePreview,
    SenseAssessment,
    SenseDecision,
    SenseDimension,
)
from khalinos.godot_gameplay import explicit_gameplay_criteria


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

Do not treat these as six mandatory survey questions. Most bounded browser projects should
need zero to three questions. Questions four through six are exceptional and require a
separate, material user-owned choice that cannot be inferred safely. Infer a dimension when the goal,
sources, previous answers, authoritative defaults, and low-risk assumptions make it clear.
Ask only when a missing choice could materially change the result, cost, authority, safety,
or visual direction. Ask exactly one concrete question at a time and no more than six
questions across one intake. Never repeat a dimension that is already answered or resolved.
Before asking, compare the candidate question with the original goal, material inspection,
confirmed answers, and every previous question. Do not ask the user to restate a requested
feature, bug report, acceptance criterion, or maker implementation choice under a different
dimension. Treat an explicit bug report as operating context, an explicitly requested feature
as a required enabler, and ordinary code cleanup as a Maker decision unless it changes scope
or authority. If the same user decision has already been supplied in different words, resolve
the dimension instead of asking again.

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

This first stage decides only whether one real user question remains. When every dimension
is sufficiently resolved, return status ready with all six resolved dimensions and no
question. Do not generate an Outcome Preview in this stage. Return only SenseAssessment.

The approved_execution_profile payload is execution authority. Every recommendation and
acceptance criterion must be feasible inside that exact profile. If the requested outcome
materially needs a capability outside it, ask under required_enablers whether to choose the
in-profile bounded outcome or stop for separate future authorization. Never describe the
profile as a full engine, arbitrary-code, production game, or existing-project repair path
unless those capabilities are explicitly present. Never recommend a forbidden dependency.
The 30-minute limit is one runaway-execution safety slice, not a user-project deadline.
The current profiles are not resumable, so the approved outcome must fit one slice. Prefer
the strongest complete, polished outcome that fits the slice. Include
recognizable standard modes, presets, and quality features when they make the requested
product materially better and remain feasible; choose them autonomously rather than turning
them into user questions. Avoid unrelated novelty and never trade away visual finish or
reliability merely to increase feature count. Apply visual competition only when the profile
explicitly includes it. Estimates must include every declared stage, stay inside the hard
safety limits, and remain realistic rather than simply equal to the maximum.

For experience_visual_direction, inspect supplied reference images concretely: composition,
hierarchy, density, typography, palette, material cues, interaction emphasis, strengths to
preserve, and weaknesses to change. A redesign question and recommendation must mention
observed qualities or the product's specific purpose. Do not use generic "SaaS dashboard",
glassmorphism, neon gradient, glowing-card, or trendy-template language as a recommended
default unless the user explicitly asks for it. Recommend one distinctive, feasible art
direction with explicit anti-goals, not a menu of fashionable styles.
""".strip()


SIXSENSE_PREVIEW_INSTRUCTION = """
You are the KHALINOS Outcome Contract editor. The SixSense assessment has resolved all six
dimensions. Produce one realistic OutcomePreview and recommended UserBrief from the supplied
goal, sources, confirmed answers, material inspection, and approved_execution_profile.
Do not ask a question. The execution profile is authority: every deliverable, technology,
completion criterion, cost, duration, and file must fit it. Preserve explicit user choices,
apply strong professional defaults where the user had no preference, and never invent an
unavailable dependency or expand authority.

For browser.product, return the exact five-file offline browser surface and include the
declared visual competition in the estimate. For godot.topology.new-product, state plainly
that the result is a bounded Godot screen-and-overlay topology prototype, not a finished
game. Its completion criteria may only require the initial screen to open, declared
screens/overlays/scenes to load or be reachable, and declared navigation/transitions to be
connected under digest-bound headless verification. Do not promise gameplay, arbitrary
scripts, input mechanics, physics, generated assets, existing-project repair, or production
3D behavior. Put the zero-repair rule under authority or constraints, never under completion
criteria. Set repairs per Quest to zero for this profile. Return only OutcomePreview.

For godot.gameplay.new-product, state plainly that the result is a bounded playable Godot
2D gameplay vertical slice, not a topology prototype and not a full production game. Bind
completion to several mechanics the approved probe can execute: formation movement, enemy
spawn and automatic combat, shared health or support effects, record/experience and level
choices, and survival victory or defeat. Include real display-backed render evidence and the
digest-bound Sprite Atlas with independent visual completeness verification. Never say that
gameplay, physics, input loops, or generated sprites are excluded. The exact authorized files
are KHALINOS_GAMEPLAY.json, KHALINOS_SPRITE_ATLAS.json, README.md,
assets/sprite-atlas.png, assets/visual-foundation.png, project.godot,
scenes/gameplay.tscn, scripts/khalinos_gameplay.gd, and
scripts/khalinos_gameplay_probe.gd. Set repairs per Quest to zero. Return only OutcomePreview.
""".strip()


_GODOT_GAMEPLAY_OUTPUTS = [
    "KHALINOS_GAMEPLAY.json",
    "KHALINOS_SPRITE_ATLAS.json",
    "README.md",
    "assets/sprite-atlas.png",
    "assets/visual-foundation.png",
    "project.godot",
    "scenes/gameplay.tscn",
    "scripts/khalinos_gameplay.gd",
    "scripts/khalinos_gameplay_probe.gd",
]

_GODOT_SIDE_SCROLL_OUTPUTS = [
    "KHALINOS_DESTINATION.json",
    "KHALINOS_SIDE_SCROLL.json",
    "README.md",
    "assets/visual-foundation.png",
    "project.godot",
    "scenes/gameplay.tscn",
    "scripts/khalinos_combat_feedback.gd",
    "scripts/khalinos_side_scroll.gd",
    "scripts/khalinos_side_scroll_probe.gd",
]

_GODOT_SIDE_SCROLL_CRITERIA = [
    "The party advances right and defeats approaching enemies automatically in the horizontal lane.",
    "The horizontal journey reaches its declared destination and reports a rendered victory state.",
]


def _explicit_gameplay_criteria(
    record: IntakeRecord,
    source_payloads: list[tuple[str, str, bytes]] | None = None,
) -> list[str]:
    """Derive mandatory mechanics from both the goal and bounded text references."""

    texts = [record.goal]
    for _name, media_type, data in source_payloads or []:
        if media_type not in {"text/plain", "text/markdown", "application/json"}:
            continue
        texts.append(data.decode("utf-8", errors="strict"))
    return explicit_gameplay_criteria("\n\n".join(texts))


def bind_preview_to_profile(
    record: IntakeRecord,
    preview: OutcomePreview,
    source_payloads: list[tuple[str, str, bytes]] | None = None,
) -> OutcomePreview:
    """Bind model-authored preview details to the already approved execution profile."""

    if record.requested_toolpack_id == "godot.side-scroll-experiment":
        acceptance = list(dict.fromkeys([
            *_GODOT_SIDE_SCROLL_CRITERIA,
            *preview.recommended_brief.acceptance_criteria,
        ]))[:10]
        completion = list(dict.fromkeys([
            *_GODOT_SIDE_SCROLL_CRITERIA,
            *preview.completion_and_quality,
        ]))[:10]
        brief = preview.recommended_brief.model_copy(update={
            "max_repairs_per_quest": 0,
            "toolpack_binding": record.requested_toolpack_binding,
            "authorized_output_files": _GODOT_SIDE_SCROLL_OUTPUTS,
            "acceptance_criteria": acceptance,
        })
        return preview.model_copy(update={
            "recommended_brief": brief,
            "completion_and_quality": completion,
        })
    if record.requested_toolpack_id != "godot.gameplay":
        return preview
    explicit = _explicit_gameplay_criteria(record, source_payloads)
    acceptance = list(dict.fromkeys([*explicit, *preview.recommended_brief.acceptance_criteria]))[:10]
    completion = list(dict.fromkeys([*explicit, *preview.completion_and_quality]))[:10]
    brief = preview.recommended_brief.model_copy(update={
        "max_repairs_per_quest": 0,
        "toolpack_binding": record.requested_toolpack_binding,
        "authorized_output_files": _GODOT_GAMEPLAY_OUTPUTS,
        "acceptance_criteria": acceptance,
    })
    return preview.model_copy(update={"recommended_brief": brief, "completion_and_quality": completion})


def validate_preview_profile(
    record: IntakeRecord,
    preview: OutcomePreview,
    source_payloads: list[tuple[str, str, bytes]] | None = None,
) -> None:
    """Fail closed when a preview silently narrows an approved gameplay route."""

    if record.requested_toolpack_id == "godot.side-scroll-experiment":
        all_text = " ".join([
            preview.final_result,
            *preview.required_enablers,
            *preview.exclusions_and_preservation,
            *preview.operating_context,
            *preview.completion_and_quality,
            *preview.authority_budget_and_delivery,
            preview.recommended_brief.goal,
            *preview.recommended_brief.acceptance_criteria,
        ]).casefold()
        forbidden = (
            "screen-and-overlay topology prototype",
            "no gameplay mechanics",
            "without gameplay mechanics",
            "no input loops",
            "topology-only",
        )
        if any(term in all_text for term in forbidden):
            raise ValueError("Godot side-scroll Preview cannot be narrowed to a topology-only outcome")
        criteria = " ".join(preview.recommended_brief.acceptance_criteria).casefold()
        required_groups = (
            ("horizontal", "side-scroll", "side scroll"),
            ("enemy", "enemies", "combat", "attack"),
            ("destination",),
            ("victory",),
        )
        if not all(any(term in criteria for term in group) for group in required_groups):
            raise ValueError("Godot side-scroll Preview must bind horizontal combat and destination victory")
        if preview.recommended_brief.authorized_output_files != _GODOT_SIDE_SCROLL_OUTPUTS:
            raise ValueError("Godot side-scroll Preview output surface must match the approved ToolPack")
        if preview.recommended_brief.toolpack_binding != record.requested_toolpack_binding:
            raise ValueError("Godot side-scroll Preview must carry the approved ToolPack binding")
        return
    if record.requested_toolpack_id != "godot.gameplay":
        return
    all_text = " ".join([
        preview.final_result,
        *preview.required_enablers,
        *preview.exclusions_and_preservation,
        *preview.operating_context,
        *preview.completion_and_quality,
        *preview.authority_budget_and_delivery,
        preview.recommended_brief.goal,
        *preview.recommended_brief.acceptance_criteria,
    ]).casefold()
    forbidden = (
        "screen-and-overlay topology prototype",
        "no gameplay mechanics",
        "without gameplay mechanics",
        "no input loops",
        "exactly 4 authorized output files",
        "delivery of exactly 4",
    )
    if any(term in all_text for term in forbidden):
        raise ValueError("Godot Gameplay Preview cannot be narrowed to a topology-only outcome")
    if "godot" not in preview.final_result.casefold() or not any(
        term in preview.final_result.casefold() for term in ("playable", "gameplay", "survival")
    ):
        raise ValueError("Godot Gameplay Preview must state the playable Godot outcome")
    criteria = " ".join(preview.recommended_brief.acceptance_criteria).casefold()
    mechanic_groups = (
        ("movement", "move", "formation"),
        ("enemy", "spawn", "attack", "combat"),
        ("health", "damage", "heal", "shield"),
        ("record", "experience", "level", "choice"),
        ("survival", "victory", "defeat", "timer", "session"),
    )
    covered = sum(any(term in criteria for term in group) for group in mechanic_groups)
    if covered < 3:
        raise ValueError("Godot Gameplay Preview must bind completion to executed mechanics")
    if preview.recommended_brief.authorized_output_files != _GODOT_GAMEPLAY_OUTPUTS:
        raise ValueError("Godot Gameplay Preview output surface must match the approved ToolPack")
    explicit = _explicit_gameplay_criteria(record, source_payloads)
    if not set(explicit).issubset(set(preview.recommended_brief.acceptance_criteria)):
        raise ValueError("Godot Gameplay Preview omitted an explicit probe-shaped user requirement")


class SixSenseAgent:
    def __init__(self) -> None:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        model = os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash")
        self.assessment_agent = LlmAgent(
            name="khalinos_sixsense_assessment",
            model=model,
            instruction=SIXSENSE_INSTRUCTION,
            output_schema=SenseAssessment,
            output_key="khalinos_sixsense_assessment_output",
            include_contents="none",
            generate_content_config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )
        self.preview_agent = LlmAgent(
            name="khalinos_sixsense_preview",
            model=model,
            instruction=SIXSENSE_PREVIEW_INSTRUCTION,
            output_schema=OutcomePreview,
            output_key="khalinos_sixsense_preview_output",
            include_contents="none",
            generate_content_config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )

    async def _structured(self, agent: LlmAgent, payload: dict, source_payloads: list[tuple[str, str, bytes]]) -> str:
        session_service = InMemorySessionService()
        session_id = uuid4().hex
        user_id = "khalinos-intake"
        app_name = agent.name
        await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
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
            raise RuntimeError(f"{agent.name} returned no structured response")
        return final_text

    async def assess(self, record: IntakeRecord, source_payloads: list[tuple[str, str, bytes]]) -> SenseDecision:
        if record.requested_toolpack_id == "godot.gameplay":
            execution_profile = {
                "profile_id": "godot.gameplay.new-product",
                "scope": "a bounded playable offline Godot 4.7.1 2D top-down gameplay vertical slice",
                "files": ["data-driven gameplay manifest", "trusted Godot scene and script", "one trusted PNG visual foundation", "runtime and render evidence"],
                "technologies": ["Godot 4.7.1", "Nano Banana", "trusted gameplay compiler", "headless mechanics probe", "real display-backed PNG capture"],
                "supported_outcomes": ["formation movement", "enemy survival loop", "automatic abilities", "summed party stats", "ordered profession choices", "bounded resurrection", "session-bound victory and defeat", "rendered gameplay evidence"],
                "forbidden": ["3D", "multiplayer", "network services", "arbitrary plugins or scripts", "existing-project repair", "production-ready full game claim"],
                "quest_limit": "2 to 5",
                "repair_limit_per_quest": "0",
                "maximum_run_budget_usd": 5,
                "maximum_duration_minutes": 30,
                "scope_rule": "bind completion only to mechanics executed by the deterministic gameplay probe and visible real Godot render",
                "visual_competition": "three Nano Banana candidates, raw asset gate, real gameplay renders, independent multimodal selection",
            }
        elif record.requested_toolpack_id == "godot.side-scroll-experiment":
            execution_profile = {
                "profile_id": "godot.side-scroll-destination.new-product",
                "scope": "a bounded playable offline Godot 4.7.1 2D horizontal auto-combat journey",
                "files": ["data-driven side-scroll and destination manifests", "trusted Godot scene and scripts", "one trusted PNG visual foundation", "runtime and render evidence"],
                "technologies": ["Godot 4.7.1", "Nano Banana", "trusted side-scroll compiler", "headless mechanics probe", "real display-backed PNG capture"],
                "supported_outcomes": ["continuous rightward travel", "horizontal lane combat", "enemy spawning", "automatic attacks", "enemy defeat", "destination progress", "victory", "visible combat feedback", "rendered gameplay evidence"],
                "forbidden": ["3D", "multiplayer", "network services", "platform jumping", "open world", "arbitrary plugins or scripts", "existing-project repair", "production-ready full game claim"],
                "quest_limit": "2 to 5",
                "repair_limit_per_quest": "0",
                "maximum_run_budget_usd": 5,
                "maximum_duration_minutes": 30,
                "scope_rule": "bind completion to horizontal combat and destination mechanics executed by the deterministic side-scroll probe and visible real Godot renders",
                "visual_competition": "three Nano Banana candidates, raw asset gate, real side-scroll gameplay renders, independent multimodal selection",
            }
        elif record.requested_toolpack_id == "godot.visual-prototype":
            execution_profile = {
                "profile_id": "godot.visual-prototype.new-product",
                "scope": "a presentation-ready offline Godot 4.7.1 visual and screen-flow prototype",
                "files": ["Godot project and scenes", "one trusted PNG visual foundation", "trusted topology and render evidence"],
                "technologies": ["Godot 4.7.1", "Nano Banana", "trusted generated scenes", "real display-backed PNG capture"],
                "supported_outcomes": ["visual direction", "connected screens", "declared transitions", "real rendered prototype evidence"],
                "forbidden": ["finished gameplay claim", "existing-project repair", "arbitrary scripts", "physics", "network services", "unbounded assets"],
                "quest_limit": "2 to 5",
                "repair_limit_per_quest": "0",
                "maximum_run_budget_usd": 5,
                "maximum_duration_minutes": 30,
                "scope_rule": "bind completion to visible render quality and bounded screen flow, never to unimplemented gameplay",
                "visual_competition": "three Nano Banana candidates, raw asset gate, real Godot renders, independent multimodal selection",
            }
        elif record.requested_project_kind == "godot":
            execution_profile = {
                "profile_id": "godot.topology.new-product",
                "scope": "a bounded offline Godot 4.7.1 screen-and-overlay topology prototype",
                "files": ["KHALINOS_TOPOLOGY.json", "project.godot", "scenes/*.tscn", "two trusted probe scripts"],
                "technologies": ["Godot 4.7.1", "trusted generated scenes", "trusted GDScript probes"],
                "supported_outcomes": ["connected screens", "overlays", "declared transitions", "headless scene loading"],
                "forbidden": ["existing-project repair", "arbitrary scripts", "gameplay mechanics", "3D production assets", "network services", "external assets"],
                "quest_limit": "2 to 5",
                "repair_limit_per_quest": "0",
                "maximum_run_budget_usd": 5,
                "maximum_duration_minutes": 30,
                "scope_rule": "state clearly that this is a topology prototype, and bind completion only to start/load/reach/connect evidence",
                "visual_competition": "not authorized",
            }
        else:
            execution_profile = {
                "profile_id": "browser.product",
                "scope": "a polished interactive offline browser micro-product",
                "files": ["index.html", "styles.css", "app.js", "journey.json", "README.md", "one trusted local PNG visual asset"],
                "technologies": ["HTML", "CSS", "inline SVG", "Canvas", "vanilla JavaScript", "Nano Banana visual asset generation"],
                "forbidden": ["CDN", "external URL", "package", "network call", "arbitrary binary asset", "data URL", "server dependency", "text baked into generated imagery"],
                "quest_limit": "2 to 5",
                "repair_limit_per_quest": "0 to 2",
                "maximum_run_budget_usd": 5,
                "maximum_duration_minutes": 30,
                "scope_rule": "prefer the smallest complete polished outcome",
                "visual_competition": "three Nano Banana asset-assisted candidates, trusted PNG validation, rendered Chromium screenshots, independent multimodal selection",
            }
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
            "previous_questions": [item.model_dump(mode="json") for item in record.question_history],
            "already_resolved_dimensions": [item.value for item in record.resolved_dimensions],
            "allowed_dimensions": [item.value for item in ALL_SENSE_DIMENSIONS],
            "requested_project_kind": record.requested_project_kind or "browser",
            "requested_toolpack_id": record.requested_toolpack_id,
            "requested_toolpack_binding": record.requested_toolpack_binding.model_dump(mode="json") if record.requested_toolpack_binding else None,
            "requested_work_mode": record.requested_work_mode,
            "approved_execution_profile": execution_profile,
        }
        assessment = SenseAssessment.model_validate(json.loads(
            await self._structured(self.assessment_agent, payload, source_payloads)
        ))
        if assessment.status == "question":
            decision = SenseDecision(
                status="question",
                resolved_dimensions=assessment.resolved_dimensions,
                next_question=assessment.next_question,
            )
        else:
            payload["sixsense_assessment"] = assessment.model_dump(mode="json")
            preview = OutcomePreview.model_validate(json.loads(
                await self._structured(self.preview_agent, payload, source_payloads)
            ))
            preview = bind_preview_to_profile(record, preview, source_payloads)
            decision = SenseDecision(
                status="ready",
                resolved_dimensions=assessment.resolved_dimensions,
                preview=preview,
            )
        validate_decision(record, decision, source_payloads)
        return decision


def validate_decision(
    record: IntakeRecord,
    decision: SenseDecision,
    source_payloads: list[tuple[str, str, bytes]] | None = None,
) -> None:
    answered = {SenseDimension(key) for key in record.answers}
    previously_resolved = set(record.resolved_dimensions)
    resolved = set(decision.resolved_dimensions)
    if not previously_resolved.issubset(resolved):
        raise ValueError("SixSense cannot reopen a resolved dimension during one intake")
    if not answered.issubset(resolved):
        raise ValueError("SixSense must preserve every confirmed answer as resolved")
    if decision.next_question:
        asked_count = max(len(record.answers), len(record.question_history))
        if asked_count >= 6:
            raise ValueError("SixSense cannot ask more than six user questions")
        dimension = decision.next_question.dimension
        if dimension in answered or dimension in resolved:
            raise ValueError("SixSense repeated an answered or resolved dimension")
        normalized_question = " ".join(decision.next_question.question.casefold().split())
        previous_questions = {" ".join(item.question.casefold().split()) for item in record.question_history}
        if normalized_question in previous_questions:
            raise ValueError("SixSense repeated a previous question")
    elif decision.preview:
        validate_preview_profile(record, decision.preview, source_payloads)
