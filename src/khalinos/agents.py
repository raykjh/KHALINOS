"""Gemini 3.5 agents executed through Google ADK."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import TypeVar
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from khalinos.browser_artifacts import BrowserArtifactBundle
from khalinos.godot_gameplay import GodotGameplayPlan, GodotGameplayProjectPlan
from khalinos.godot_side_scroll import GodotSideScrollPlan, GodotSideScrollProjectPlan
from khalinos.godot_topology import GodotProjectPlan, GodotTopologyPlan
from khalinos.models import (
    AgentVerification,
    ArtifactAsset,
    ArtifactBundle,
    QuestPlan,
    UserBrief,
    VisualConcept,
    VisualAssetGate,
    SpriteAtlasGate,
    VisualConceptPlan,
    VisualSelection,
)
from khalinos.visual_assets import generate_visual_asset
from khalinos.sprite_assets import SpriteAtlasPlan, generate_sprite_atlas


MODEL = os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash")
T = TypeVar("T", bound=BaseModel)


def compact_vertex_json_schema(schema: type[BaseModel]) -> dict[str, object]:
    """Return the small JSON-schema subset needed to shape model output.

    Vertex rejects overly complex structured-output schemas with an opaque 400.
    KHALINOS keeps all numeric, pattern, cross-reference, and authority checks in
    the trusted Pydantic validator after generation, so the model-facing schema
    only needs to preserve object shape, required fields, arrays, and enums.
    """

    source = schema.model_json_schema()
    definitions = source.get("$defs", {})

    def compact(node: object) -> object:
        if not isinstance(node, dict):
            return node
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            return compact(definitions[reference.rsplit("/", 1)[-1]])

        result: dict[str, object] = {}
        if "type" in node:
            result["type"] = node["type"]
        if "enum" in node:
            result["enum"] = node["enum"]
        elif "const" in node:
            result["enum"] = [node["const"]]
        properties = node.get("properties")
        if isinstance(properties, dict):
            result["properties"] = {name: compact(value) for name, value in properties.items()}
        if "required" in node:
            result["required"] = node["required"]
        if "items" in node:
            result["items"] = compact(node["items"])
        return result

    compacted = compact(source)
    if not isinstance(compacted, dict):
        raise TypeError("model JSON schema did not compact to an object")
    return compacted


def normalize_structured_result(schema: type[BaseModel], result: object) -> object:
    """Normalize presentation-only model variance before strict validation."""

    if schema is QuestPlan and isinstance(result, dict):
        # The model does not possess authority to mint a ToolPack binding. Vertex
        # may still emit an empty object for this optional schema field; collapse
        # that presentation artifact to ``None`` so the trusted workflow can bind
        # the exact approved manifest after validation.
        if result.get("toolpack_binding") == {}:
            result["toolpack_binding"] = None
        for key in ("product_summary", "architecture_decision"):
            value = result.get(key)
            if isinstance(value, str) and len(value) > 800:
                result[key] = value[:797].rstrip() + "..."
        quests = result.get("quests", [])
        if isinstance(quests, list):
            for index, quest in enumerate(quests, start=1):
                if not isinstance(quest, dict):
                    continue
                quest["quest_id"] = f"Q{index}"
                quest["depends_on"] = [] if index == 1 else [f"Q{index - 1}"]
    if schema is GodotGameplayPlan and isinstance(result, dict):
        role_order = result.get("upgrade_role_order")
        if isinstance(role_order, list):
            result["upgrade_role_order"] = list(dict.fromkeys(role_order))
        for collection in ("heroes", "enemies"):
            for item in result.get(collection, []):
                if isinstance(item, dict) and isinstance(item.get("color_hex"), str):
                    item["color_hex"] = item["color_hex"].removeprefix("#")
        for ability in result.get("abilities", []):
            if (
                isinstance(ability, dict)
                and ability.get("kind") == "resurrection"
                and isinstance(ability.get("radius"), (int, float))
                and ability["radius"] < 20
            ):
                # Resurrection is a stored party-state transition, not a spatial
                # effect. Bind its schema-only radius to the trusted minimum instead
                # of weakening numeric validation or rerunning the whole planner.
                ability["radius"] = 20
    return result


OWNER_INSTRUCTION = """
You are the KHALINOS Project Owner. Convert the approved user brief into a short,
linear sequence of outcome-bound quests. Each quest must be independently verifiable
and must shape the same browser micro-application incrementally. Use two to five quests,
never widen the supplied goal, constraints, files, budget, or acceptance criteria, and
never ask the user or a coding assistant to design later steps. Quest acceptance_criteria
may use only verbatim strings from the approved brief, and the complete plan must cover every
approved criterion. Put test files, journey structure, source inspection, and documentation
requirements in evidence_required, never in acceptance_criteria. Do not turn KHALINOS's
verification machinery into a user-facing product feature unless the approved brief asks for
it. Return only the required schema.
""".strip()

MAKER_INSTRUCTION = """
You are the accountable KHALINOS Maker. Produce the complete current revision of one
self-contained browser micro-application for the active Quest. Return exactly five files:
index.html, styles.css, app.js, journey.json, and README.md. Use only HTML, CSS, and
vanilla JavaScript. No external URLs, packages, network calls, embedded data URLs,
eval, dynamic code loading, analytics, or placeholder TODOs. The UI must be in English,
responsive, keyboard accessible, visually coherent, and actually interactive.

journey.json must contain {"journeys":[...]} with at least one journey. Each journey has
a name, a criterion field containing one exact active-Quest acceptance-criterion string or
one exact required_regression_criteria string that it proves, an optional random_seed integer,
and ordered steps. Every active and regression criterion must have direct runtime evidence;
preserve previously verified journeys and add separate journeys when needed. Supported typed steps are
{"click":"CSS selector"}, {"right_click":"CSS selector"}, {"press":"Keyboard key"},
{"wait_ms":1..12000},
{"assert_text":{"selector":"CSS selector","operator":"eq|contains","value":"visible text"}},
{"assert_count":{"selector":"CSS selector","operator":"eq|gt|gte|lt|lte","value":integer}},
{"assert_attribute":{"selector":"CSS selector","name":"attribute","operator":"eq|contains|not_equals","value":"text"}},
{"assert_class":{"selector":"CSS selector","includes":["class"],"excludes":["class"]}},
or {"assert_state":{"selector":"CSS selector","state":"visible|hidden|enabled|disabled|checked|unchecked"}}.
Do not emit arbitrary JavaScript. Every active criterion must be named by exactly one or more journeys
and backed by a selector-targeted typed assertion that observes its runtime result; never use
unscoped {"assert_text":"text"} in a criterion-bound journey. Clicks, waits, screenshots,
source code, and README claims alone are not proof. Selectors must point to real controls in
index.html and the journey must prove the active Quest behavior. Preserve
working behavior from the previous verified bundle and make only changes needed for the
current Quest. When the previous bundle is an approved visual foundation, preserve its
composition, typography, palette, material language, and anti-goals while adding behavior.
If the previous bundle contains the trusted assets/visual-foundation.png image, preserve its
exact relative reference and data-khalinos-asset="visual-foundation" element. The host, not
the Maker, owns and reattaches its verified bytes.
Keep revision_summary concise and under 500 characters. Return only the required schema.
""".strip()

VERIFIER_INSTRUCTION = """
You are the independent KHALINOS Verifier. You did not create the artifact and cannot
modify it. Judge every active Quest acceptance criterion against the supplied complete
artifact and deterministic browser evidence. PASS only when every criterion has direct
evidence. A file existing, a claim in README, or the maker's assertion is not proof of
runtime behavior. If any criterion fails, return concise repair instructions tied only to
that criterion. Return findings in the exact supplied criterion order. The host, not you,
binds those ordered findings back to the immutable criterion text. Never weaken criteria or
approve missing evidence. Return only the schema.
""".strip()

REPAIR_INSTRUCTION = """
You are the KHALINOS Technical Repair Agent. Repair the complete artifact bundle using
the active Quest plus deterministic failures and independent verifier instructions. For an
existing_project_entry, the validated supplied bundle is the authoritative starting point:
make only the bounded change required by the active Quest and preserve everything else.
Preserve all previously verified behavior. Do not change the Quest, criteria, authorized files,
or invent a different journey schema.
If the failed bundle contains the trusted assets/visual-foundation.png image, preserve its exact
relative reference and data-khalinos-asset="visual-foundation" element. Never synthesize,
encode, replace, or remove the host-owned image bytes.
If the incoming artifact uses a legacy or incomplete journey, migrate it to the current typed
journey contract, bind every exact active and required regression criterion to direct runtime
assertions, and do not
weaken the criterion while doing so.
Keep revision_summary concise and under 500 characters. Return the complete five-file bundle
and only the required schema.
""".strip()

VISUAL_DIRECTOR_INSTRUCTION = """
You are the KHALINOS Visual Director. Read the approved brief and its bound visual
direction, then issue exactly three genuinely different but equally feasible visual concepts
for the same product. Differences must be structural: composition, hierarchy, type system,
material language, and interaction emphasis, not merely color swaps. Every concept must fit
the approved ToolPack and render surface supplied in the request, preserve usability, and
state concrete anti-goals that prevent generic template output. Do not widen product scope.
Return only the required schema.
""".strip()

VISUAL_MAKER_INSTRUCTION = """
You are the KHALINOS Visual Candidate Maker. Materialize one supplied visual concept as a
complete five-file browser artifact: index.html, styles.css, app.js, journey.json, and
README.md. Create a presentation-ready representative state with enough real interaction to
prove hierarchy, controls, responsive composition, and visual identity in Chromium. Follow
the concept precisely and honor all anti-goals. Use HTML, CSS, inline SVG, Canvas, and vanilla
JavaScript only. One trusted local PNG is supplied at assets/visual-foundation.png. Render it
exactly once as <img src="assets/visual-foundation.png"
data-khalinos-asset="visual-foundation" alt=""> in a supporting environmental layer. Keep all
UI, labels, icons, and state in accessible HTML/CSS; the page must remain understandable if the
image fails to load. No other external URL, package, network call, data URL, placeholder, or
unfinished control. Every form control must have an explicit label or aria-label, and icon-only buttons
must have aria-labels.

journey.json must contain exactly the wrapper {"journeys":[...]} with at least one journey.
Each visual-foundation journey has a name and ordered steps. A step must use the same typed
journey actions documented for the Maker, including {"click":"CSS selector"},
{"press":"Keyboard key"}, and {"assert_text":"visible text"}. Visual foundations must omit
criterion because no Quest is active during visual selection. Do not use type, selector, text, or key fields as
a different step schema, and never emit arbitrary JavaScript. The journey must
exercise real controls and produce a meaningful rendered screenshot. Keep revision_summary
concise and under 500 characters. Return only the required schema.
""".strip()

VISUAL_VERIFIER_INSTRUCTION = """
You are the independent KHALINOS Visual Verifier. You did not create the candidates and
cannot modify them. Compare the two or three eligible real rendered product screenshots against
the approved visual contract and each concept. Score contract alignment, visual hierarchy,
distinctiveness, interaction clarity, and craft/cohesion from 1 to 10. Penalize generic SaaS
templates, superficial color variation, weak typography, cramped density, unclear primary
action, or divergence from explicit anti-goals. Judge visible evidence rather than README or
maker claims. Assess only candidates identified as eligible and shown in screenshots, ordered
by candidate ID. Select the candidate with the highest rubric average; ties may be resolved
by stronger contract alignment, then distinctiveness. Return only the required schema.
""".strip()

VISUAL_ASSET_VERIFIER_INSTRUCTION = """
You are the independent KHALINOS Visual Asset Gate. You did not generate the supplied PNG
and cannot modify it. Inspect the raw image itself, not a rendered browser screenshot. Reject
it if any readable text, letter, number, word-like glyph sequence, logo, watermark, signature,
button, panel, HUD, label, chart annotation, rune, inscription, carving, symbol, signage,
interface-like geometry, decorative marking, or other interface element is visible. Do not
make exceptions for marks that appear abstract or non-linguistic. Approve only a pure supporting
environmental image that can sit behind trusted accessible UI. Return only the required schema,
using the supplied candidate_id exactly.
""".strip()

SPRITE_ATLAS_VERIFIER_INSTRUCTION = """
You are the independent KHALINOS Sprite Atlas Gate. You did not generate the supplied
normalized PNG and cannot modify it. Compare the image with the exact supplied slot plan.
Approve only when every assigned cell contains exactly one complete, centered character;
the count and order match; heroes and enemies are readily distinguishable; and all sprites
share one coherent scale, lighting, outline, and rendering style. Reject text, glyphs, UI,
logos, watermarks, extra characters, clipped bodies or weapons, overlapping cells, scenery,
animation frames, checkerboards, halos, or other background residue. Inspect every slot
individually. A head, torso, hand, foot, weapon, shield, bow, staff, cape, horn, or other
role-defining equipment that is missing or materially erased is a completeness failure even
when the remaining pixels occupy a valid bounding box. Return one slot_finding in exact plan
order and use each supplied sprite_id exactly. Return only the required schema.
""".strip()

GODOT_QUEST_OWNER_INSTRUCTION = """
You are the KHALINOS Godot Project Owner issuing the Quest chain for one immutable
approved brief. You do not write gameplay plans, topology regions, GDScript, scenes, commands, files,
tests, executable paths, or verification code. The trusted Godot ToolPack owns those.
Issue two to five linear Quests without inventing features, network services, assets, or
mechanics outside the brief. Quest acceptance_criteria may use only verbatim strings from
the approved brief, every approved criterion must appear exactly once across the chain,
and no criterion may be omitted or added. Put trusted compilation, runtime execution,
file inspection, rendered capture, and receipt requirements only in evidence_required.
The model must not set or alter the ToolPack binding. Return only the required QuestPlan.
Keep product_summary and architecture_decision below 700 characters each.
""".strip()

GODOT_TOPOLOGY_OWNER_INSTRUCTION = """
You are the KHALINOS Godot Project Owner materializing the bounded topology decision for
the supplied immutable brief and already-issued QuestPlan. You do not write GDScript,
scenes, commands, files, tests, executable paths, or verification code. Return only a
GodotTopologyPlan containing two to sixteen connected screen or overlay regions with
explicit directed transitions and one initial region. Use the approved project_name
exactly. Infer only the minimum conventional screen topology required by the brief and
QuestPlan. Do not invent product features, network services, assets, or mechanics.
Return only the required GodotTopologyPlan schema.
""".strip()

GODOT_GAMEPLAY_OWNER_INSTRUCTION = """
You are the KHALINOS Godot Gameplay Planner. Convert the immutable approved brief and
already-issued QuestPlan into one bounded data-driven 2D top-down gameplay plan. You do
not write GDScript, scenes, commands, files, tests, executable paths, or verification
code. The trusted compiler owns implementation. Use the approved project_name exactly.
Model only heroes, enemy archetypes, scheduled automatic abilities, summed shared party
stats, session duration, and deterministic level-choice cadence supported by the supplied
ToolPack manifest. Explicit numeric duration and cadence requirements are mandatory, not
suggestions. When the brief requires profession progression, provide Tank, Damage, and
Support profession rosters, the exact upgrade_role_order, and exactly three choices per
level: current-profession rank-up first and two alternative professions. When resurrection
is required, declare capacity one and exactly one automatic resurrection ability. Preserve
requested roles and session length exactly. Do not
invent networking, 3D, plugins, backend services, save systems, arbitrary mechanics, or
production scope. Return only the required GodotGameplayPlan schema.
Every identifier must start with a lowercase letter and contain only lowercase letters,
digits, and underscores. Every color_hex must contain exactly six hexadecimal characters
without a leading '#'. Keep hero health within 20..10000, attack and defense within
their declared bounds, hero move_speed within 40..800, enemy speed within 10..500,
ability radius within 20..1000, and all other numeric values within the supplied schema.
""".strip()

GODOT_VERIFIER_INSTRUCTION = """
You are the independent KHALINOS Godot Verifier. You did not plan or materialize the
artifact and cannot modify it. Judge each active Quest acceptance criterion only from
the immutable brief, structured approved Godot plan, compiled artifact digests, and supplied
digest-bound Godot headless and display-render evidence. Return findings in the exact supplied criterion
order, with exactly one finding for every criterion in quest.acceptance_criteria. Treat
the supplied deterministic_evidence criterion mapping and typed runtime probe as primary
runtime evidence; a screenshot is not required to show every temporal state. PASS only
when each criterion has direct deterministic evidence; a plan, source
file, README claim, or Project Owner assertion alone is not runtime proof. Never weaken
criteria or broaden authority. Return only the required schema.
""".strip()


GODOT_SIDE_SCROLL_OWNER_INSTRUCTION = """
You are the existing KHALINOS Godot Gameplay Owner slot temporarily rebound to the approved
side-scroll profile. Materialize only the bounded structured plan requested by the immutable
brief and approved Quest plan. The party advances left-to-right on one horizontal lane,
attacks automatically, encounters bounded enemies, and wins at one declared destination.
Do not add platform jumping, arbitrary scripts, multiplayer, inventory, backend services,
or production-game claims. Keep every numeric value within the supplied schema and preserve
the approved project name exactly. Return only the required schema.
""".strip()


def _agent(
    name: str,
    instruction: str,
    schema: type[T],
    *,
    temperature: float,
    max_output_tokens: int = 8192,
    compact_json_schema: bool = False,
) -> LlmAgent:
    structured_schema = compact_vertex_json_schema(schema) if compact_json_schema else None
    return LlmAgent(
        name=name,
        model=MODEL,
        instruction=instruction,
        output_schema=None if compact_json_schema else schema,
        output_key=f"{name}_output",
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            response_mime_type="application/json" if compact_json_schema else None,
            response_json_schema=structured_schema,
        ),
    )


class AgentTeam:
    """Role-separated ADK agents; Python enforces the approved state machines."""

    def __init__(self) -> None:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        self.owner = _agent("khalinos_project_owner", OWNER_INSTRUCTION, QuestPlan, temperature=0.1)
        self.maker = _agent(
            "khalinos_accountable_maker",
            MAKER_INSTRUCTION,
            BrowserArtifactBundle,
            temperature=0.25,
            max_output_tokens=49_152,
        )
        self.verifier = _agent("khalinos_independent_verifier", VERIFIER_INSTRUCTION, AgentVerification, temperature=0.0)
        self.repairer = _agent(
            "khalinos_technical_repair",
            REPAIR_INSTRUCTION,
            BrowserArtifactBundle,
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
            BrowserArtifactBundle,
            temperature=0.4,
            max_output_tokens=49_152,
        )
        self.visual_verifier = _agent(
            "khalinos_visual_verifier",
            VISUAL_VERIFIER_INSTRUCTION,
            VisualSelection,
            temperature=0.0,
        )
        self.visual_asset_verifier = _agent(
            "khalinos_visual_asset_verifier",
            VISUAL_ASSET_VERIFIER_INSTRUCTION,
            VisualAssetGate,
            temperature=0.0,
        )
        self.sprite_atlas_verifier = _agent(
            "khalinos_sprite_atlas_verifier",
            SPRITE_ATLAS_VERIFIER_INSTRUCTION,
            SpriteAtlasGate,
            temperature=0.0,
        )
        self.godot_quest_owner = _agent(
            "khalinos_godot_quest_owner",
            GODOT_QUEST_OWNER_INSTRUCTION,
            QuestPlan,
            temperature=0.1,
            compact_json_schema=True,
        )
        self.godot_topology_owner = _agent(
            "khalinos_godot_topology_owner",
            GODOT_TOPOLOGY_OWNER_INSTRUCTION,
            GodotTopologyPlan,
            temperature=0.1,
        )
        self.godot_gameplay_owner = _agent(
            "khalinos_godot_gameplay_owner",
            GODOT_GAMEPLAY_OWNER_INSTRUCTION,
            GodotGameplayPlan,
            temperature=0.1,
            compact_json_schema=True,
        )
        self.godot_verifier = _agent(
            "khalinos_godot_independent_verifier",
            GODOT_VERIFIER_INSTRUCTION,
            AgentVerification,
            temperature=0.0,
        )
        self.call_count = 0
        self.call_count_by_agent: dict[str, int] = {}
        self._image_lock = asyncio.Lock()
        self._last_image_call_started = 0.0

    def _record_call(self, agent_id: str) -> None:
        self.call_count += 1
        self.call_count_by_agent[agent_id] = self.call_count_by_agent.get(agent_id, 0) + 1

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
        self._record_call(agent.name)
        if not final_text:
            raise RuntimeError(f"{agent.name} returned no structured response")
        result = normalize_structured_result(schema, json.loads(final_text))
        return schema.model_validate(result)

    async def plan(self, payload: dict) -> QuestPlan:
        return await self._run(self.owner, payload, QuestPlan)

    async def plan_godot(self, payload: dict) -> GodotProjectPlan:
        quest_plan = await self._run(self.godot_quest_owner, payload, QuestPlan)
        topology = await self._run(
            self.godot_topology_owner,
            {**payload, "approved_quest_plan": quest_plan.model_dump(mode="json")},
            GodotTopologyPlan,
        )
        return GodotProjectPlan(quest_plan=quest_plan, topology=topology)

    async def plan_godot_gameplay(self, payload: dict) -> GodotGameplayProjectPlan:
        quest_plan = await self._run(self.godot_quest_owner, payload, QuestPlan)
        gameplay = await self._run(
            self.godot_gameplay_owner,
            {**payload, "approved_quest_plan": quest_plan.model_dump(mode="json")},
            GodotGameplayPlan,
        )
        return GodotGameplayProjectPlan(quest_plan=quest_plan, gameplay=gameplay)

    async def plan_godot_side_scroll(self, payload: dict) -> GodotSideScrollProjectPlan:
        """Reuse the existing gameplay-owner slot with a side-scroll output contract."""

        quest_plan = await self._run(self.godot_quest_owner, payload, QuestPlan)
        rebound_owner = _agent(
            self.godot_gameplay_owner.name,
            GODOT_SIDE_SCROLL_OWNER_INSTRUCTION,
            GodotSideScrollPlan,
            temperature=0.1,
            compact_json_schema=True,
        )
        gameplay = await self._run(
            rebound_owner,
            {**payload, "approved_quest_plan": quest_plan.model_dump(mode="json")},
            GodotSideScrollPlan,
        )
        return GodotSideScrollProjectPlan(quest_plan=quest_plan, gameplay=gameplay)

    async def make(self, payload: dict) -> ArtifactBundle:
        result = await self._run(self.maker, payload, BrowserArtifactBundle)
        return result.to_artifact_bundle()

    async def verify(self, payload: dict) -> AgentVerification:
        return await self._run(self.verifier, payload, AgentVerification)

    async def verify_godot(self, payload: dict) -> AgentVerification:
        return await self._run(self.godot_verifier, payload, AgentVerification)

    async def repair(self, payload: dict) -> ArtifactBundle:
        result = await self._run(self.repairer, payload, BrowserArtifactBundle)
        return result.to_artifact_bundle()

    async def plan_visuals(self, payload: dict) -> VisualConceptPlan:
        return await self._run(self.visual_director, payload, VisualConceptPlan)

    async def make_visual(self, payload: dict) -> ArtifactBundle:
        result = await self._run(self.visual_maker, payload, BrowserArtifactBundle)
        return result.to_artifact_bundle()

    async def make_visual_asset(self, brief: UserBrief, concept: VisualConcept) -> ArtifactAsset:
        minimum_interval = float(os.environ.get("KHALINOS_IMAGE_MIN_INTERVAL_SECONDS", "35"))
        async with self._image_lock:
            elapsed = time.monotonic() - self._last_image_call_started
            if self._last_image_call_started and elapsed < minimum_interval:
                await asyncio.sleep(minimum_interval - elapsed)
            self._last_image_call_started = time.monotonic()
            asset = await asyncio.to_thread(generate_visual_asset, brief, concept)
            self._record_call(self.visual_maker.name)
            return asset

    async def verify_visual_asset(
        self,
        candidate_id: str,
        asset: ArtifactAsset,
        concept: VisualConcept,
    ) -> VisualAssetGate:
        return await self._run(
            self.visual_asset_verifier,
            {
                "candidate_id": candidate_id,
                "approved_visual_concept": concept.model_dump(mode="json"),
                "asset_manifest": {
                    "path": asset.path,
                    "sha256": asset.sha256,
                    "width": asset.width,
                    "height": asset.height,
                },
            },
            VisualAssetGate,
            extra_parts=[types.Part.from_bytes(data=asset.bytes(), mime_type=asset.media_type)],
        )

    async def make_sprite_atlas(
        self,
        brief: UserBrief,
        concept: VisualConcept,
        plan: SpriteAtlasPlan,
        feedback: tuple[str, ...] = (),
    ) -> ArtifactAsset:
        minimum_interval = float(os.environ.get("KHALINOS_IMAGE_MIN_INTERVAL_SECONDS", "35"))
        async with self._image_lock:
            def before_model_call() -> None:
                elapsed = time.monotonic() - self._last_image_call_started
                if self._last_image_call_started and elapsed < minimum_interval:
                    time.sleep(minimum_interval - elapsed)
                self._last_image_call_started = time.monotonic()
                self._record_call(self.visual_maker.name)

            return await asyncio.to_thread(
                generate_sprite_atlas,
                brief,
                concept,
                plan,
                feedback,
                before_model_call,
            )

    async def verify_sprite_atlas(
        self,
        plan: SpriteAtlasPlan,
        asset: ArtifactAsset,
        concept: VisualConcept,
    ) -> SpriteAtlasGate:
        gate = await self._run(
            self.sprite_atlas_verifier,
            {
                "approved_visual_concept": concept.model_dump(mode="json"),
                "sprite_atlas_plan": plan.model_dump(mode="json"),
                "asset_manifest": {
                    "path": asset.path,
                    "sha256": asset.sha256,
                    "width": asset.width,
                    "height": asset.height,
                },
            },
            SpriteAtlasGate,
            extra_parts=[types.Part.from_bytes(data=asset.bytes(), mime_type=asset.media_type)],
        )
        expected_ids = [slot.sprite_id for slot in plan.slots]
        actual_ids = [finding.sprite_id for finding in gate.slot_findings]
        if actual_ids != expected_ids:
            raise RuntimeError("sprite atlas verifier findings do not exactly match the approved slot plan")
        return gate

    async def select_visual(self, payload: dict, screenshots: list[tuple[str, bytes]]) -> VisualSelection:
        parts: list[types.Part] = []
        for candidate_id, data in screenshots:
            parts.append(types.Part.from_text(text=f"Trusted rendered product screenshot for {candidate_id}"))
            parts.append(types.Part.from_bytes(data=data, mime_type="image/png"))
        return await self._run(
            self.visual_verifier,
            payload,
            VisualSelection,
            extra_parts=parts,
        )
