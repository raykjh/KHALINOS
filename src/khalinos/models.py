"""Strict contracts exchanged by the KHALINOS agent team."""

from __future__ import annotations

import hashlib
import json
import re
import base64
import struct
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.json_schema import SkipJsonSchema

from khalinos.toolpacks import ToolPackBinding


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_sha256(value: BaseModel | dict | list) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class RunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    VISUALIZING = "visualizing"
    VISUAL_SELECTING = "visual_selecting"
    EXECUTING = "executing"
    RUNTIME_CHECKING = "runtime_checking"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    PASSED = "passed"
    BLOCKED = "blocked"
    FAILED = "failed"


class AuthoritativeReference(BaseModel):
    filename: str = Field(min_length=1, max_length=160)
    media_type: Literal["text/plain", "text/markdown", "application/json"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content: str = Field(min_length=1, max_length=100_000)


class UserBrief(BaseModel):
    project_name: str = Field(min_length=2, max_length=80)
    goal: str = Field(min_length=30, max_length=5000)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    acceptance_criteria: list[str] = Field(min_length=2, max_length=10)
    max_quests: int = Field(default=4, ge=2, le=5)
    max_repairs_per_quest: int = Field(default=2, ge=0, le=2)
    toolpack_binding: ToolPackBinding | None = None
    authorized_output_files: list[str] = Field(min_length=1, max_length=256)
    # Execution-only authority. The Outcome Preview model must not reproduce source
    # documents inside its structured-output schema; authorization injects them later.
    authoritative_references: SkipJsonSchema[list[AuthoritativeReference]] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def safe_output_surface(self) -> "UserBrief":
        if len(set(self.authorized_output_files)) != len(self.authorized_output_files):
            raise ValueError("authorized output paths must be unique")
        for path in self.authorized_output_files:
            normalized = path.replace("\\", "/")
            parts = normalized.split("/")
            if (
                not path
                or normalized.startswith("/")
                or ":" in parts[0]
                or any(part in {"", ".", ".."} for part in parts)
            ):
                raise ValueError("authorized output paths must stay relative to the artifact root")
        if sum(len(item.content.encode("utf-8")) for item in self.authoritative_references) > 200_000:
            raise ValueError("authoritative reference text exceeds 200 KB")
        return self


class SenseDimension(StrEnum):
    REQUIRED_ENABLERS = "required_enablers"
    EXCLUSIONS_PRESERVATION = "exclusions_preservation"
    EXPERIENCE_VISUAL_DIRECTION = "experience_visual_direction"
    OPERATING_CONTEXT = "operating_context"
    COMPLETION_QUALITY_STANDARD = "completion_quality_standard"
    AUTHORITY_BUDGET_DELIVERY = "authority_budget_delivery"


ALL_SENSE_DIMENSIONS = list(SenseDimension)


class SourceUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=160)
    media_type: str = Field(pattern=r"^(text/plain|text/markdown|application/json|application/zip|image/png|image/jpeg|image/webp)$")
    data_base64: str = Field(min_length=1, max_length=14_000_000)


class SourceReference(BaseModel):
    source_id: str
    filename: str
    media_type: str
    size_bytes: int = Field(ge=1, le=10_000_000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class MaterialDescriptor(BaseModel):
    filename: str = Field(min_length=1, max_length=260)
    relative_path: str = Field(min_length=1, max_length=1000)
    media_type: str = Field(default="application/octet-stream", max_length=160)
    size_bytes: int = Field(ge=0, le=5_000_000_000)

    @model_validator(mode="after")
    def safe_relative_path(self) -> "MaterialDescriptor":
        normalized = self.relative_path.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if not parts or normalized.startswith("/") or ":" in parts[0] or any(part in {".", ".."} for part in parts):
            raise ValueError("material relative_path must be a safe relative path")
        if parts[-1] != self.filename:
            raise ValueError("material filename must match the relative_path basename")
        return self


class MaterialInspectionRequest(BaseModel):
    project_locator: str = Field(default="", max_length=2000)
    materials: list[MaterialDescriptor] = Field(default_factory=list, max_length=5000)


class MaterialInspection(BaseModel):
    project_kind: Literal["godot", "unity", "web", "unknown", "none"]
    recommended_work_mode: Literal[
        "new_product_build",
        "existing_project_work",
        "reproduce_and_repair",
        "black_box_diagnosis",
        "reference_guided_build",
    ]
    source_available: bool
    runnable_build_available: bool
    material_count: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    detected_materials: list[str] = Field(default_factory=list, max_length=12)
    summary: str = Field(min_length=10, max_length=800)
    notices: list[str] = Field(default_factory=list, max_length=8)


class ArchiveSnapshot(BaseModel):
    """Immutable, validated source archive admitted to an execution contract."""

    bucket: str = Field(min_length=1, max_length=255)
    object_name: str = Field(min_length=1, max_length=1024)
    generation: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=1, le=200_000_000)
    project_kind: Literal["browser"] = "browser"
    root_prefix: str = Field(default="", max_length=500)
    entry_count: int = Field(ge=5, le=1000)
    uncompressed_size_bytes: int = Field(ge=1, le=25_000_000)
    materials: list[MaterialDescriptor] = Field(min_length=5, max_length=6)


class UploadCreate(BaseModel):
    filename: str = Field(pattern=r"^[^/\\]{1,160}\.zip$")
    size_bytes: int = Field(ge=1, le=200_000_000)


class UploadRecord(BaseModel):
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner_id: str = Field(min_length=3, max_length=255)
    filename: str
    expected_size_bytes: int = Field(ge=1, le=200_000_000)
    object_name: str
    status: Literal["pending", "finalized", "rejected"] = "pending"
    snapshot: ArchiveSnapshot | None = None
    rejection_reason: str | None = Field(default=None, max_length=500)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class IntakeCreate(BaseModel):
    project_name: str = Field(min_length=2, max_length=80)
    goal: str = Field(min_length=20, max_length=5000)
    sources: list[SourceUpload] = Field(default_factory=list, max_length=8)
    project_locator: str = Field(default="", max_length=2000)
    materials: list[MaterialDescriptor] = Field(default_factory=list, max_length=5000)
    selected_project_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    requested_project_kind: Literal["browser", "godot"] | None = None
    requested_toolpack_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    requested_toolpack_binding: ToolPackBinding | None = None
    requested_work_mode: Literal["new_product_build", "existing_project_repair"] = "new_product_build"


class RouteRecommendationRequest(BaseModel):
    project_name: str = Field(min_length=2, max_length=80)
    goal: str = Field(min_length=20, max_length=5000)
    project_locator: str = Field(default="", max_length=2000)
    materials: list[MaterialDescriptor] = Field(default_factory=list, max_length=5000)
    requested_work_mode: Literal["new_product_build"] = "new_product_build"


class RouteCandidateAssessment(BaseModel):
    toolpack_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    fit: Literal["exact", "bounded_alternative", "incompatible"]
    reason: str = Field(min_length=15, max_length=500)
    expected_result: str = Field(min_length=20, max_length=700)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class RouteRecommendation(BaseModel):
    status: Literal["recommended", "unsupported"]
    recommended_toolpack_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    candidates: list[RouteCandidateAssessment] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def valid_recommendation(self) -> "RouteRecommendation":
        ids = [item.toolpack_id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("route candidates must be unique")
        by_id = {item.toolpack_id: item for item in self.candidates}
        if self.status == "recommended":
            if self.recommended_toolpack_id not in by_id:
                raise ValueError("recommended route must name one returned candidate")
            if by_id[self.recommended_toolpack_id].fit == "incompatible":
                raise ValueError("an incompatible route cannot be recommended")
        elif self.recommended_toolpack_id is not None:
            raise ValueError("unsupported route decisions cannot recommend a ToolPack")
        return self


ShortAnswerOption = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=48)]


class SenseQuestion(BaseModel):
    dimension: SenseDimension
    question: str = Field(min_length=15, max_length=240)
    answer_options: list[ShortAnswerOption] = Field(min_length=2, max_length=4)
    why_it_matters: str = Field(min_length=10, max_length=240)

    @model_validator(mode="after")
    def concise_distinct_choices(self) -> "SenseQuestion":
        normalized = [item.strip().casefold() for item in self.answer_options]
        if len(normalized) != len(set(normalized)):
            raise ValueError("answer options must be distinct")
        return self


class ExecutionEstimate(BaseModel):
    quest_count: int = Field(ge=2, le=5)
    cost_usd_min: float = Field(ge=0, le=5)
    cost_usd_max: float = Field(ge=0, le=5)
    duration_minutes_min: int = Field(ge=1, le=30)
    duration_minutes_max: int = Field(ge=1, le=30)

    @model_validator(mode="after")
    def ordered_ranges(self) -> "ExecutionEstimate":
        if self.cost_usd_min > self.cost_usd_max:
            raise ValueError("cost range must be ordered")
        if self.duration_minutes_min > self.duration_minutes_max:
            raise ValueError("duration range must be ordered")
        return self


class OutcomePreview(BaseModel):
    final_result: str = Field(min_length=30, max_length=1200)
    required_enablers: list[str] = Field(min_length=1, max_length=10)
    exclusions_and_preservation: list[str] = Field(min_length=1, max_length=10)
    visual_direction: str = Field(min_length=20, max_length=1200)
    operating_context: list[str] = Field(min_length=1, max_length=10)
    completion_and_quality: list[str] = Field(min_length=2, max_length=10)
    authority_budget_and_delivery: list[str] = Field(min_length=1, max_length=10)
    estimate: ExecutionEstimate
    recommended_brief: UserBrief


class SenseDecision(BaseModel):
    status: Literal["question", "ready"]
    resolved_dimensions: list[SenseDimension] = Field(default_factory=list, max_length=6)
    next_question: SenseQuestion | None = None
    preview: OutcomePreview | None = None

    @model_validator(mode="after")
    def valid_transition(self) -> "SenseDecision":
        if len(self.resolved_dimensions) != len(set(self.resolved_dimensions)):
            raise ValueError("resolved dimensions must be unique")
        if self.status == "question" and (self.next_question is None or self.preview is not None):
            raise ValueError("question decisions require exactly one next question")
        if self.status == "ready":
            if self.preview is None or self.next_question is not None:
                raise ValueError("ready decisions require exactly one preview")
            if set(self.resolved_dimensions) != set(ALL_SENSE_DIMENSIONS):
                raise ValueError("ready decisions must resolve all SixSense dimensions")
        return self


class SenseAssessment(BaseModel):
    """Small first-stage schema that never carries the large Outcome Preview."""

    status: Literal["question", "ready"]
    resolved_dimensions: list[SenseDimension] = Field(default_factory=list, max_length=6)
    next_question: SenseQuestion | None = None

    @model_validator(mode="after")
    def valid_transition(self) -> "SenseAssessment":
        if len(self.resolved_dimensions) != len(set(self.resolved_dimensions)):
            raise ValueError("resolved dimensions must be unique")
        if self.status == "question" and self.next_question is None:
            raise ValueError("question assessments require one next question")
        if self.status == "ready":
            if self.next_question is not None:
                raise ValueError("ready assessments cannot include a question")
            if set(self.resolved_dimensions) != set(ALL_SENSE_DIMENSIONS):
                raise ValueError("ready assessments must resolve all SixSense dimensions")
        return self


class IntakeAnswer(BaseModel):
    dimension: SenseDimension
    answer: str = Field(min_length=2, max_length=3000)


class IntakeRevision(BaseModel):
    change_request: str = Field(min_length=2, max_length=2000)


class IntakeReroute(BaseModel):
    """A user-confirmed replacement ToolPack for an existing Outcome Preview."""

    requested_project_kind: Literal["browser", "godot"]
    requested_toolpack_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    requested_toolpack_binding: ToolPackBinding


class IntakeRecord(BaseModel):
    intake_id: str
    status: Literal["sensing", "ready", "authorized"] = "sensing"
    project_name: str
    goal: str
    sources: list[SourceReference] = Field(default_factory=list)
    project_locator: str = ""
    material_inspection: MaterialInspection | None = None
    owner_id: str = ""
    selected_project_id: str | None = None
    source_snapshot: ArchiveSnapshot | None = None
    requested_project_kind: Literal["browser", "godot"] | None = None
    requested_toolpack_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    requested_toolpack_binding: ToolPackBinding | None = None
    requested_work_mode: Literal["new_product_build", "existing_project_repair"] = "new_product_build"
    answers: dict[str, str] = Field(default_factory=dict)
    resolved_dimensions: list[SenseDimension] = Field(default_factory=list)
    question_history: list[SenseQuestion] = Field(default_factory=list, max_length=6)
    current_question: SenseQuestion | None = None
    preview: OutcomePreview | None = None
    authorized_run_id: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class QuestSpec(BaseModel):
    quest_id: str = Field(pattern=r"^Q[1-5]$")
    objective: str = Field(min_length=20, max_length=500)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=8)
    evidence_required: list[str] = Field(min_length=1, max_length=8)
    depends_on: list[str] = Field(default_factory=list, max_length=1)


class QuestPlan(BaseModel):
    product_summary: str = Field(min_length=30, max_length=800)
    architecture_decision: str = Field(min_length=30, max_length=800)
    toolpack_binding: ToolPackBinding | None = None
    quests: list[QuestSpec] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def linear_chain(self) -> "QuestPlan":
        expected = [f"Q{index}" for index in range(1, len(self.quests) + 1)]
        if [quest.quest_id for quest in self.quests] != expected:
            raise ValueError("quests must be a contiguous Q1..Qn sequence")
        for index, quest in enumerate(self.quests):
            required = [] if index == 0 else [expected[index - 1]]
            if quest.depends_on != required:
                raise ValueError("quests must form one receipt-gated linear chain")
        return self


class ArtifactFile(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    content: str = Field(min_length=1, max_length=2_000_000)

    @model_validator(mode="after")
    def safe_relative_path(self) -> "ArtifactFile":
        normalized = self.path.replace("\\", "/")
        parts = normalized.split("/")
        if (
            normalized.startswith("/")
            or ":" in parts[0]
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ValueError("artifact path must stay relative to the artifact root")
        return self


class ArtifactAsset(BaseModel):
    path: str = Field(pattern=r"^assets/[a-z0-9][a-z0-9._-]{0,79}\.png$")
    media_type: Literal["image/png"] = "image/png"
    data_base64: str = Field(min_length=12, max_length=4_000_000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: int = Field(ge=256, le=2048)
    height: int = Field(ge=256, le=2048)

    @model_validator(mode="after")
    def digest_matches_payload(self) -> "ArtifactAsset":
        try:
            payload = base64.b64decode(self.data_base64, validate=True)
        except ValueError as exc:
            raise ValueError("artifact asset must contain valid base64") from exc
        if hashlib.sha256(payload).hexdigest() != self.sha256:
            raise ValueError("artifact asset digest does not match its payload")
        if not 1_024 <= len(payload) <= 2_500_000:
            raise ValueError("artifact asset size is outside the approved bound")
        if len(payload) < 24 or not payload.startswith(b"\x89PNG\r\n\x1a\n") or payload[12:16] != b"IHDR":
            raise ValueError("artifact asset must contain a PNG IHDR header")
        actual_width, actual_height = struct.unpack(">II", payload[16:24])
        if (actual_width, actual_height) != (self.width, self.height):
            raise ValueError("artifact asset dimensions do not match its PNG payload")
        if actual_width * actual_height > 4_000_000:
            raise ValueError("artifact asset pixel count exceeds the approved bound")
        return self

    def bytes(self) -> bytes:
        return base64.b64decode(self.data_base64, validate=True)


class ArtifactBundle(BaseModel):
    revision_summary: str = Field(min_length=10, max_length=2000)
    files: list[ArtifactFile] = Field(min_length=1, max_length=256)
    assets: list[ArtifactAsset] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def unique_file_set(self) -> "ArtifactBundle":
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths must be unique")
        asset_paths = [item.path for item in self.assets]
        if len(asset_paths) != len(set(asset_paths)):
            raise ValueError("artifact asset paths must be unique")
        if set(paths).intersection(asset_paths):
            raise ValueError("artifact text and binary paths must be unique")
        return self

    def file_map(self) -> dict[str, str]:
        return {item.path: item.content for item in self.files}

    def asset_map(self) -> dict[str, ArtifactAsset]:
        return {item.path: item for item in self.assets}


class VisualConcept(BaseModel):
    candidate_id: str = Field(pattern=r"^V[1-3]$")
    name: str = Field(min_length=3, max_length=80)
    design_thesis: str = Field(min_length=30, max_length=800)
    composition: str = Field(min_length=20, max_length=800)
    typography: str = Field(min_length=15, max_length=500)
    palette: list[str] = Field(min_length=3, max_length=8)
    interaction_emphasis: str = Field(min_length=20, max_length=500)
    anti_goals: list[str] = Field(min_length=2, max_length=8)


class VisualConceptPlan(BaseModel):
    shared_contract: str = Field(min_length=30, max_length=1000)
    candidates: list[VisualConcept] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def three_distinct_candidates(self) -> "VisualConceptPlan":
        if [item.candidate_id for item in self.candidates] != ["V1", "V2", "V3"]:
            raise ValueError("visual candidates must be ordered V1, V2, V3")
        if len({item.name.casefold() for item in self.candidates}) != 3:
            raise ValueError("visual candidates must have distinct names")
        return self


class VisualAssetGate(BaseModel):
    candidate_id: str = Field(pattern=r"^V[1-3]$")
    approved: bool
    contains_text_or_glyphs: bool
    contains_interface_elements: bool
    contains_logo_or_watermark: bool
    issues: list[str] = Field(default_factory=list, max_length=6)
    rationale: str = Field(min_length=20, max_length=600)

    @model_validator(mode="after")
    def forbidden_content_cannot_be_approved(self) -> "VisualAssetGate":
        forbidden = self.contains_text_or_glyphs or self.contains_interface_elements or self.contains_logo_or_watermark
        if self.approved == forbidden:
            raise ValueError("visual asset approval must reject every forbidden-content signal")
        if forbidden and not self.issues:
            raise ValueError("rejected visual assets require a concrete issue")
        return self


class SpriteSlotVisualFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sprite_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    complete_full_body: bool
    required_equipment_preserved: bool
    background_residue_absent: bool
    role_is_readable: bool
    issue: str | None = Field(default=None, min_length=3, max_length=300)

    @model_validator(mode="after")
    def issue_matches_signals(self) -> "SpriteSlotVisualFinding":
        safe = all((
            self.complete_full_body,
            self.required_equipment_preserved,
            self.background_residue_absent,
            self.role_is_readable,
        ))
        if safe == (self.issue is not None):
            raise ValueError("sprite slot issue must be present exactly when a completeness signal fails")
        return self


class SpriteAtlasGate(BaseModel):
    """Independent semantic gate for one normalized gameplay sprite atlas."""

    approved: bool
    slot_count_matches: bool
    roles_are_distinguishable: bool
    style_is_consistent: bool
    contains_text_or_glyphs: bool
    contains_interface_elements: bool
    contains_logo_or_watermark: bool
    has_clipped_or_overlapping_sprites: bool
    all_characters_complete: bool
    all_required_equipment_preserved: bool
    background_residue_absent: bool
    slot_findings: list[SpriteSlotVisualFinding] = Field(min_length=1, max_length=12)
    issues: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(min_length=20, max_length=800)

    @model_validator(mode="after")
    def approval_matches_signals(self) -> "SpriteAtlasGate":
        safe = (
            self.slot_count_matches
            and self.roles_are_distinguishable
            and self.style_is_consistent
            and not self.contains_text_or_glyphs
            and not self.contains_interface_elements
            and not self.contains_logo_or_watermark
            and not self.has_clipped_or_overlapping_sprites
            and self.all_characters_complete
            and self.all_required_equipment_preserved
            and self.background_residue_absent
            and all(
                item.complete_full_body
                and item.required_equipment_preserved
                and item.background_residue_absent
                and item.role_is_readable
                for item in self.slot_findings
            )
        )
        if self.approved != safe:
            raise ValueError("sprite atlas approval must match every semantic safety signal")
        if not safe and not self.issues:
            raise ValueError("rejected sprite atlases require a concrete issue")
        return self


class VisualAssessment(BaseModel):
    candidate_id: str = Field(pattern=r"^V[1-3]$")
    contract_alignment: int = Field(ge=1, le=10)
    visual_hierarchy: int = Field(ge=1, le=10)
    distinctiveness: int = Field(ge=1, le=10)
    interaction_clarity: int = Field(ge=1, le=10)
    craft_and_cohesion: int = Field(ge=1, le=10)
    strengths: list[str] = Field(min_length=1, max_length=5)
    weaknesses: list[str] = Field(default_factory=list, max_length=5)

    def score(self) -> float:
        return sum([
            self.contract_alignment,
            self.visual_hierarchy,
            self.distinctiveness,
            self.interaction_clarity,
            self.craft_and_cohesion,
        ]) / 5


class VisualSelection(BaseModel):
    assessments: list[VisualAssessment] = Field(min_length=2, max_length=3)
    selected_candidate_id: str = Field(pattern=r"^V[1-3]$")
    rationale: str = Field(min_length=30, max_length=1000)

    @model_validator(mode="after")
    def selected_candidate_has_top_score(self) -> "VisualSelection":
        ids = [item.candidate_id for item in self.assessments]
        expected_order = [item for item in ["V1", "V2", "V3"] if item in ids]
        if ids != expected_order or len(ids) != len(set(ids)):
            raise ValueError("eligible visual assessments must be unique and ordered")
        if self.selected_candidate_id not in ids:
            raise ValueError("selected visual candidate must be assessed")
        scores = {item.candidate_id: item.score() for item in self.assessments}
        if scores[self.selected_candidate_id] != max(scores.values()):
            raise ValueError("selected visual candidate must have the highest rubric score")
        return self


class VisualSelectionReceipt(BaseModel):
    receipt_id: str
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_candidate_id: str = Field(pattern=r"^V[1-3]$")
    selected_artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    eligible_candidate_ids: list[str] = Field(min_length=2, max_length=3)
    screenshot_paths: dict[str, str]
    asset_sha256_by_candidate: dict[str, str] = Field(default_factory=dict)
    selection: VisualSelection
    created_at: str = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def assets_match_eligible_candidates(self) -> "VisualSelectionReceipt":
        if set(self.asset_sha256_by_candidate) != set(self.eligible_candidate_ids):
            raise ValueError("visual asset receipts must match the eligible candidates exactly")
        if any(not re.fullmatch(r"[a-f0-9]{64}", digest) for digest in self.asset_sha256_by_candidate.values()):
            raise ValueError("visual asset receipt digests must be SHA-256 values")
        return self


class CriterionFinding(BaseModel):
    criterion: str = Field(min_length=3, max_length=500)
    passed: bool
    evidence: str = Field(min_length=3, max_length=1000)


class AgentVerification(BaseModel):
    findings: list[CriterionFinding] = Field(min_length=1, max_length=10)
    verdict: Literal["PASS", "REPAIR"]
    repair_instructions: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def consistent_verdict(self) -> "AgentVerification":
        all_pass = all(item.passed for item in self.findings)
        if (self.verdict == "PASS") != all_pass:
            raise ValueError("verdict must match criterion findings")
        if self.verdict == "REPAIR" and not self.repair_instructions:
            raise ValueError("a repair verdict requires bounded repair instructions")
        return self


class DeterministicEvidence(BaseModel):
    passed: bool
    checks: dict[str, bool]
    issues: list[str]
    screenshot_names: list[str] = Field(default_factory=list)
    criterion_evidence: dict[str, list[str]] = Field(default_factory=dict)


class QuestReceipt(BaseModel):
    receipt_id: str
    quest_id: str
    quest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_receipt_id: str | None = None
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    toolpack_binding: ToolPackBinding | None = None
    deterministic_evidence: DeterministicEvidence
    independent_verification: AgentVerification
    repair_rounds: int = Field(ge=0, le=2)
    state: Literal["passed", "blocked"]
    created_at: str = Field(default_factory=utc_now)


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    brief_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    toolpack_binding: ToolPackBinding | None = None
    current_quest_id: str | None = None
    completed_receipt_ids: list[str] = Field(default_factory=list)
    message: str
    model: str = "gemini-3.5-flash"
    framework: str = "Google ADK 2.6.2"
    cloud_services: list[str] = Field(
        default_factory=lambda: ["Vertex AI", "Cloud Run", "Cloud Storage", "Firestore"]
    )
    cloud_project_id: str = ""
    cloud_region: str = ""
    cloud_job_name: str = ""
    cloud_operation_name: str = ""
    cloud_execution_id: str = ""
    model_calls: int = 0
    owner_id: str = ""
    project_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    work_mode: Literal["new_product_build", "existing_project_repair"] = "new_product_build"
    source_snapshot: ArchiveSnapshot | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


SAFE_RUN_ID = re.compile(r"^[a-f0-9]{32}$")


class ProjectRecord(BaseModel):
    project_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner_id: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=2, max_length=80)
    project_kind: Literal["browser", "godot", "unity", "web", "unknown"] = "browser"
    origin: Literal["khalinos", "external"] = "khalinos"
    latest_run_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    latest_status: RunStatus
    latest_checkpoint_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    latest_receipt_ids: list[str] = Field(default_factory=list)
    source_snapshot: ArchiveSnapshot | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
