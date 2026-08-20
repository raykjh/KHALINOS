from __future__ import annotations

import base64

import pytest

from khalinos.intake import answer_intake, authorized_brief, bind_material_role, inspect_materials, reroute_intake, restart_intake, start_intake
from khalinos.intake_storage import LocalIntakeStore
from khalinos.models import (
    ALL_SENSE_DIMENSIONS,
    ExecutionEstimate,
    IntakeAnswer,
    IntakeCreate,
    IntakeReroute,
    IntakeRevision,
    MaterialDescriptor,
    MaterialInspectionRequest,
    OutcomePreview,
    SenseDecision,
    SenseDimension,
    SenseQuestion,
    SourceUpload,
    UserBrief,
)
from khalinos.toolpacks import ToolPackBinding
from khalinos.sixsense import bind_preview_to_profile, validate_decision


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
            authorized_output_files=["README.md", "app.js", "index.html", "journey.json", "styles.css"],
        ),
    )


def test_explicit_new_project_treats_uploaded_archive_as_reference_not_existing_work() -> None:
    inspection = inspect_materials(MaterialInspectionRequest(materials=[
        MaterialDescriptor(filename="Trinity-Survivors-Input.zip", relative_path="Trinity-Survivors-Input.zip", media_type="application/zip", size_bytes=16000),
    ]))
    assert inspection.recommended_work_mode == "existing_project_work"
    bound = bind_material_role(inspection, requested_work_mode="new_product_build")
    assert bound.recommended_work_mode == "reference_guided_build"
    assert bound.source_available is False
    assert "new product" in bound.summary.lower()
    assert any("Reference inputs" in item for item in bound.detected_materials)


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
                    answer_options=["Editorial and warm", "Minimal and neutral", "Playful and colorful"],
                    why_it_matters="Visual direction materially changes layout, styling, and the evidence used for approval.",
                ),
            )
        return SenseDecision(
            status="ready",
            resolved_dimensions=ALL_SENSE_DIMENSIONS,
            preview=preview(),
        )


class MemoryIntakeStore:
    """Small fixture-free store for state-transition contract tests."""

    def __init__(self) -> None:
        self.records = {}
        self.payloads = {}

    def create(self, record, sources) -> None:
        self.records[record.intake_id] = record
        for reference, data in sources:
            self.payloads[(record.intake_id, reference.source_id)] = data

    def read(self, intake_id):
        return self.records[intake_id]

    def update(self, record) -> None:
        self.records[record.intake_id] = record

    def source_bytes(self, intake_id, reference):
        return self.payloads[(intake_id, reference.source_id)]


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
    assert record.question_history == [record.current_question]
    assert record.requested_project_kind is None

    record = await answer_intake(
        record.intake_id,
        IntakeAnswer(
            dimension=SenseDimension.EXPERIENCE_VISUAL_DIRECTION,
            answer=record.current_question.answer_options[0],
        ),
        store=store,
        agent=agent,
    )
    assert record.status == "ready"
    assert set(record.resolved_dimensions) == set(ALL_SENSE_DIMENSIONS)
    assert agent.source_counts == [1, 1]


def test_material_inspection_routes_source_and_build_to_reproduce_and_repair() -> None:
    result = inspect_materials(MaterialInspectionRequest(materials=[
        MaterialDescriptor(filename="project.godot", relative_path="puzzle/project.godot", media_type="text/plain", size_bytes=400),
        MaterialDescriptor(filename="player.gd", relative_path="puzzle/scripts/player.gd", media_type="text/plain", size_bytes=2400),
        MaterialDescriptor(filename="puzzle.exe", relative_path="build/puzzle.exe", size_bytes=109_000_000),
    ]))
    assert result.project_kind == "godot"
    assert result.recommended_work_mode == "reproduce_and_repair"
    assert result.source_available is True
    assert result.runnable_build_available is True


def test_material_inspection_does_not_promise_repair_from_executable_alone() -> None:
    result = inspect_materials(MaterialInspectionRequest(materials=[
        MaterialDescriptor(filename="puzzle.exe", relative_path="puzzle.exe", size_bytes=109_000_000),
    ]))
    assert result.recommended_work_mode == "black_box_diagnosis"
    assert result.source_available is False
    assert any("cannot be promised" in notice for notice in result.notices)


def test_material_inspection_detects_unity_folder_structure() -> None:
    result = inspect_materials(MaterialInspectionRequest(materials=[
        MaterialDescriptor(filename="Player.cs", relative_path="Assets/Scripts/Player.cs", media_type="text/plain", size_bytes=1000),
        MaterialDescriptor(filename="ProjectVersion.txt", relative_path="ProjectSettings/ProjectVersion.txt", media_type="text/plain", size_bytes=30),
    ]))
    assert result.project_kind == "unity"
    assert result.recommended_work_mode == "existing_project_work"


async def test_revision_keeps_sources_and_restarts_discovery(tmp_path) -> None:
    store = LocalIntakeStore(tmp_path)
    agent = AdaptiveFake()
    request = IntakeCreate(
        project_name="Decision product",
        goal="Create a complete team decision product with a polished and responsive interface.",
        sources=[SourceUpload(filename="facts.txt", media_type="text/plain", data_base64=base64.b64encode(b"facts").decode())],
        project_locator="https://github.com/example/project.git",
        materials=[MaterialDescriptor(filename="project.godot", relative_path="project.godot", size_bytes=400)],
        requested_project_kind="godot",
    )
    first = await start_intake(request, store=store, agent=agent)
    first = await answer_intake(
        first.intake_id,
        IntakeAnswer(dimension=first.current_question.dimension, answer=first.current_question.answer_options[0]),
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
    assert revised.project_locator == first.project_locator
    assert revised.material_inspection == first.material_inspection
    assert revised.requested_project_kind == "godot"
    assert "Requested revision" in revised.goal
    assert store.source_bytes(revised.intake_id, revised.sources[0]) == b"facts"


async def test_new_godot_intake_preserves_explicit_runtime_authority(tmp_path) -> None:
    record = await start_intake(
        IntakeCreate(
            project_name="Route Observatory",
            goal="Create a bounded Godot screen topology with an arrival, workspace, and result screen.",
            requested_project_kind="godot",
            requested_work_mode="new_product_build",
        ),
        store=LocalIntakeStore(tmp_path),
        agent=AdaptiveFake(),
    )
    assert record.requested_project_kind == "godot"
    assert record.requested_work_mode == "new_product_build"


async def test_same_route_is_idempotent_and_preserves_ready_preview() -> None:
    store = MemoryIntakeStore()
    agent = AdaptiveFake()
    binding = ToolPackBinding(toolpack_id="godot.gameplay", version="1.2.0", manifest_sha256="a" * 64)
    first = await start_intake(
        IntakeCreate(
            project_name="Trinity Survivors",
            goal="Create a playable ten-minute Godot survival game with a three-hero party.",
            requested_project_kind="godot",
            requested_toolpack_id="godot.gameplay",
            requested_toolpack_binding=binding,
        ),
        store=store,
        agent=agent,
    )
    first = await answer_intake(
        first.intake_id,
        IntakeAnswer(dimension=first.current_question.dimension, answer="Tight Formation"),
        store=store,
        agent=agent,
    )
    calls_before = agent.calls
    same = await reroute_intake(
        first.intake_id,
        IntakeReroute(
            requested_project_kind="godot",
            requested_toolpack_id="godot.gameplay",
            requested_toolpack_binding=binding,
        ),
        store=store,
        agent=agent,
    )
    assert same.intake_id == first.intake_id
    assert same.preview == first.preview
    assert same.answers == first.answers
    assert agent.calls == calls_before


async def test_real_route_change_preserves_goal_sources_and_confirmed_answers() -> None:
    store = MemoryIntakeStore()
    agent = AdaptiveFake()
    old_binding = ToolPackBinding(toolpack_id="godot.gameplay", version="1.2.0", manifest_sha256="a" * 64)
    first = await start_intake(
        IntakeCreate(
            project_name="Trinity Survivors",
            goal="Create a playable ten-minute Godot survival game with a three-hero party.",
            sources=[SourceUpload(filename="rules.md", media_type="text/markdown", data_base64=base64.b64encode(b"ten minute run").decode())],
            requested_project_kind="godot",
            requested_toolpack_id="godot.gameplay",
            requested_toolpack_binding=old_binding,
        ),
        store=store,
        agent=agent,
    )
    first = await answer_intake(
        first.intake_id,
        IntakeAnswer(dimension=first.current_question.dimension, answer="Tight Formation"),
        store=store,
        agent=agent,
    )
    new_binding = ToolPackBinding(toolpack_id="godot.visual-prototype", version="1.0.0", manifest_sha256="b" * 64)
    changed = await reroute_intake(
        first.intake_id,
        IntakeReroute(
            requested_project_kind="godot",
            requested_toolpack_id="godot.visual-prototype",
            requested_toolpack_binding=new_binding,
        ),
        store=store,
        agent=agent,
    )
    assert changed.intake_id != first.intake_id
    assert changed.goal == first.goal
    assert changed.answers == first.answers
    assert changed.resolved_dimensions == first.resolved_dimensions
    assert changed.sources == first.sources
    assert store.source_bytes(changed.intake_id, changed.sources[0]) == b"ten minute run"
    assert changed.requested_toolpack_binding == new_binding


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
            answer_options=["Approved browser runtime only", "Request a future capability"],
            why_it_matters="The dependency changes feasibility and execution authority.",
        ),
    )
    with pytest.raises(ValueError, match="repeated"):
        validate_decision(record, decision)


def test_sixsense_cannot_repeat_a_previous_question_in_another_turn() -> None:
    previous = SenseQuestion(
        dimension=SenseDimension.EXPERIENCE_VISUAL_DIRECTION,
        question="Should the finished game use a classic or modern visual direction?",
        answer_options=["Classic", "Modern"],
        why_it_matters="The choice changes the visual language of the finished game.",
    )
    record = __import__("khalinos.models", fromlist=["IntakeRecord"]).IntakeRecord(
        intake_id="c" * 32,
        project_name="Minesweeper",
        goal="Repair a classic Minesweeper game while preserving its custom mechanics.",
        question_history=[previous],
    )
    decision = SenseDecision(
        status="question",
        resolved_dimensions=[],
        next_question=previous.model_copy(update={"dimension": SenseDimension.OPERATING_CONTEXT}),
    )
    with pytest.raises(ValueError, match="previous question"):
        validate_decision(record, decision)


def test_sixsense_question_requires_short_real_choices() -> None:
    with pytest.raises(ValueError, match="distinct"):
        SenseQuestion(
            dimension=SenseDimension.EXPERIENCE_VISUAL_DIRECTION,
            question="Should the finished game use a classic or modern visual direction?",
            answer_options=["Classic", "classic"],
            why_it_matters="The choice changes the visual language of the finished game.",
        )
    with pytest.raises(ValueError, match="48 characters"):
        SenseQuestion(
            dimension=SenseDimension.EXPERIENCE_VISUAL_DIRECTION,
            question="Should the finished game use a classic or modern visual direction?",
            answer_options=["Classic", "A detailed modern option with implementation instructions and feature requirements"],
            why_it_matters="The choice changes the visual language of the finished game.",
        )


def test_sixsense_stops_asking_after_six_user_decisions() -> None:
    record = __import__("khalinos.models", fromlist=["IntakeRecord"]).IntakeRecord(
        intake_id="b" * 32,
        project_name="Minesweeper",
        goal="Create a classic Minesweeper game for a modern web browser.",
        answers={
            SenseDimension.REQUIRED_ENABLERS.value: "Use approved runtime",
            SenseDimension.EXCLUSIONS_PRESERVATION.value: "No external network",
            SenseDimension.EXPERIENCE_VISUAL_DIRECTION.value: "Classic",
            SenseDimension.OPERATING_CONTEXT.value: "Desktop only",
            SenseDimension.COMPLETION_QUALITY_STANDARD.value: "Safe first click",
            SenseDimension.AUTHORITY_BUDGET_DELIVERY.value: "Use standard profile",
        },
        resolved_dimensions=ALL_SENSE_DIMENSIONS,
    )
    decision = SenseDecision(
        status="question",
        resolved_dimensions=record.resolved_dimensions,
        next_question=SenseQuestion(
            dimension=SenseDimension.AUTHORITY_BUDGET_DELIVERY,
            question="Should KHALINOS use the standard bounded delivery profile?",
            answer_options=["Use standard profile", "Stop before execution"],
            why_it_matters="This determines whether autonomous execution is authorized.",
        ),
    )
    with pytest.raises(ValueError, match="more than six"):
        validate_decision(record, decision)


def test_gameplay_preview_cannot_collapse_back_to_topology() -> None:
    record = __import__("khalinos.models", fromlist=["IntakeRecord"]).IntakeRecord(
        intake_id="d" * 32,
        project_name="Trinity Survivors",
        goal="Create a playable 2D Godot survival game with combat, health, and level choices.",
        requested_project_kind="godot",
        requested_toolpack_id="godot.gameplay",
        resolved_dimensions=ALL_SENSE_DIMENSIONS,
    )
    topology = preview().model_copy(update={
        "final_result": "A bounded Godot screen-and-overlay topology prototype with connected scenes only.",
        "exclusions_and_preservation": ["No gameplay mechanics or input loops are included."],
    })
    decision = SenseDecision(
        status="ready",
        resolved_dimensions=ALL_SENSE_DIMENSIONS,
        preview=bind_preview_to_profile(record, topology),
    )

    with pytest.raises(ValueError, match="topology-only"):
        validate_decision(record, decision)


def test_gameplay_preview_is_bound_to_exact_output_surface_and_mechanics() -> None:
    record = __import__("khalinos.models", fromlist=["IntakeRecord"]).IntakeRecord(
        intake_id="e" * 32,
        project_name="Trinity Survivors",
        goal="Create a playable 2D Godot survival game with combat, health, and level choices.",
        requested_project_kind="godot",
        requested_toolpack_id="godot.gameplay",
        resolved_dimensions=ALL_SENSE_DIMENSIONS,
    )
    gameplay = preview().model_copy(update={
        "final_result": "A bounded playable Godot 2D survival gameplay vertical slice with rendered evidence.",
        "completion_and_quality": [
            "Formation movement and enemy spawn combat pass the runtime probe.",
            "Shared health, level choices, and survival victory or defeat pass the runtime probe.",
        ],
        "recommended_brief": preview().recommended_brief.model_copy(update={
            "goal": "Create a bounded playable Godot survival gameplay vertical slice with rendered evidence.",
            "acceptance_criteria": [
                "Formation movement and enemy spawn combat pass the runtime probe.",
                "Shared health, level choices, and survival victory or defeat pass the runtime probe.",
            ],
        }),
    })
    bound = bind_preview_to_profile(record, gameplay)
    decision = SenseDecision(
        status="ready",
        resolved_dimensions=ALL_SENSE_DIMENSIONS,
        preview=bound,
    )

    validate_decision(record, decision)
    assert bound.recommended_brief.max_repairs_per_quest == 0
    assert bound.recommended_brief.authorized_output_files == [
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


def test_authorization_binds_visual_direction_and_quality_to_execution_brief() -> None:
    outcome = preview()
    brief = authorized_brief(outcome)
    assert any(item.startswith("Approved visual direction:") for item in brief.constraints)
    assert set(outcome.completion_and_quality).issubset(set(brief.acceptance_criteria))
    assert brief.max_quests == outcome.estimate.quest_count
    assert brief.goal == outcome.final_result


def test_godot_authorization_uses_only_profile_bounded_brief_criteria() -> None:
    outcome = preview().model_copy(update={
        "completion_and_quality": [
            "All declared screens load in headless verification.",
            "Zero repairs allowed per Quest.",
        ]
    })
    brief = authorized_brief(outcome, include_preview_quality=False)
    assert brief.acceptance_criteria == outcome.recommended_brief.acceptance_criteria


async def test_rejects_source_path_traversal(tmp_path) -> None:
    request = IntakeCreate(
        project_name="Decision product",
        goal="Create a complete team decision product with a polished and responsive interface.",
        sources=[SourceUpload(filename="../secret.txt", media_type="text/plain", data_base64=base64.b64encode(b"x").decode())],
    )
    with pytest.raises(ValueError, match="filename"):
        await start_intake(request, store=LocalIntakeStore(tmp_path), agent=AdaptiveFake())
