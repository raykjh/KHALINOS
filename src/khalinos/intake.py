"""SixSense intake state transitions before execution authorization."""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from khalinos.models import (
    ArchiveSnapshot,
    IntakeAnswer,
    IntakeCreate,
    IntakeRecord,
    IntakeRevision,
    MaterialInspection,
    MaterialInspectionRequest,
    OutcomePreview,
    SenseDecision,
    SourceReference,
)


def inspect_materials(request: MaterialInspectionRequest) -> MaterialInspection:
    """Classify submitted material names without opening or executing untrusted products."""
    paths = [item.relative_path.replace("\\", "/").lower() for item in request.materials]
    names = [item.filename.lower() for item in request.materials]
    locator = request.project_locator.strip().lower()
    is_godot = any(path.endswith("/project.godot") or path == "project.godot" for path in paths)
    has_unity_assets = any(path.startswith("assets/") or "/assets/" in path for path in paths)
    has_unity_settings = any(path.startswith("projectsettings/") or "/projectsettings/" in path for path in paths)
    is_unity = has_unity_assets and has_unity_settings
    is_web = any(name in {"package.json", "index.html", "vite.config.js", "vite.config.ts"} for name in names)
    project_kind = "godot" if is_godot else "unity" if is_unity else "web" if is_web else "unknown" if paths or locator else "none"

    source_suffixes = (".gd", ".cs", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".py", ".go", ".rs")
    archive_suffixes = (".zip", ".tar", ".tgz", ".tar.gz")
    runnable_suffixes = (".exe", ".app", ".apk", ".x86_64", ".appimage", ".wasm")
    locator_is_source = bool(
        locator.startswith(("git@", "ssh://", "gs://", "khalinos://"))
        or locator.endswith(".git")
        or any(host in locator for host in ("github.com/", "gitlab.com/", "bitbucket.org/"))
    )
    source_available = bool(
        is_godot
        or is_unity
        or is_web
        or locator_is_source
        or any(path.endswith(source_suffixes + archive_suffixes) for path in paths)
    )
    runnable_available = any(path.endswith(runnable_suffixes) for path in paths)
    reference_available = any(
        path.endswith((".png", ".jpg", ".jpeg", ".webp", ".md", ".txt", ".json", ".pdf"))
        for path in paths
    )

    if source_available and runnable_available:
        mode = "reproduce_and_repair"
    elif source_available:
        mode = "existing_project_work"
    elif runnable_available:
        mode = "black_box_diagnosis"
    elif reference_available:
        mode = "reference_guided_build"
    else:
        mode = "new_product_build"

    detected: list[str] = []
    if project_kind != "none":
        detected.append(f"{project_kind.capitalize()} project indicators")
    if locator:
        detected.append("Project location supplied")
    if source_available:
        detected.append("Source or project material")
    if runnable_available:
        detected.append("Runnable build")
    if reference_available:
        detected.append("Reference material")
    notices: list[str] = []
    if runnable_available and not source_available:
        notices.append("A runnable build supports black-box diagnosis, but repair cannot be promised without source material.")
    if request.materials:
        notices.append("Submitted files were classified statically and were not executed.")
    if any(path.endswith(archive_suffixes) for path in paths):
        notices.append("An archive is treated as possible source material until its contents are validated in an authorized sandbox.")
    if locator and not locator_is_source:
        notices.append("The supplied project location is descriptive until a supported connector validates it.")

    labels = {
        "new_product_build": "No existing source project was detected; KHALINOS recommends a new product build.",
        "existing_project_work": "Existing source material was detected; KHALINOS recommends work on the supplied project.",
        "reproduce_and_repair": "Source material and a runnable build were detected; KHALINOS recommends reproduce-and-repair work.",
        "black_box_diagnosis": "Only a runnable build was detected; KHALINOS recommends black-box diagnosis before any repair commitment.",
        "reference_guided_build": "Reference material was detected without a source project; KHALINOS recommends a reference-guided build.",
    }
    return MaterialInspection(
        project_kind=project_kind,
        recommended_work_mode=mode,
        source_available=source_available,
        runnable_build_available=runnable_available,
        material_count=len(request.materials),
        total_size_bytes=sum(item.size_bytes for item in request.materials),
        detected_materials=detected[:12],
        summary=labels[mode],
        notices=notices,
    )


class IntakeStore(Protocol):
    def create(self, record: IntakeRecord, sources: list[tuple[SourceReference, bytes]]) -> None: ...
    def read(self, intake_id: str) -> IntakeRecord: ...
    def update(self, record: IntakeRecord) -> None: ...
    def source_bytes(self, intake_id: str, reference: SourceReference) -> bytes: ...


class SensingAgent(Protocol):
    async def assess(self, record: IntakeRecord, source_payloads: list[tuple[str, str, bytes]]) -> SenseDecision: ...


def authorized_brief(preview: OutcomePreview):
    """Bind the confirmed SixSense outcome to the immutable execution contract."""
    source = preview.recommended_brief
    constraints = list(source.constraints[:6])
    constraints.extend(f"Exclusion or preservation: {item}" for item in preview.exclusions_and_preservation[:3])
    constraints.append(f"Approved visual direction: {preview.visual_direction}")
    constraints.extend(f"Operating context: {item}" for item in preview.operating_context[:2])
    criteria = list(dict.fromkeys([
        *source.acceptance_criteria,
        *preview.completion_and_quality,
    ]))[:10]
    return source.model_copy(update={
        "goal": preview.final_result,
        "constraints": constraints[:12],
        "acceptance_criteria": criteria,
        "max_quests": preview.estimate.quest_count,
    })


def decode_sources(request: IntakeCreate) -> list[tuple[SourceReference, bytes]]:
    decoded: list[tuple[SourceReference, bytes]] = []
    total = 0
    for upload in request.sources:
        safe_name = Path(upload.filename).name
        if safe_name != upload.filename or safe_name in {"", ".", ".."}:
            raise ValueError("source filename must not contain a path")
        try:
            data = base64.b64decode(upload.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"invalid base64 source: {safe_name}") from exc
        if not data or len(data) > 10_000_000:
            raise ValueError(f"source must contain 1 byte to 10 MB: {safe_name}")
        total += len(data)
        if total > 20_000_000:
            raise ValueError("combined source size exceeds 20 MB")
        reference = SourceReference(
            source_id=uuid4().hex,
            filename=safe_name,
            media_type=upload.media_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        decoded.append((reference, data))
    return decoded


def source_payloads(store: IntakeStore, record: IntakeRecord) -> list[tuple[str, str, bytes]]:
    return [
        (reference.filename, reference.media_type, store.source_bytes(record.intake_id, reference))
        for reference in record.sources
    ]


def apply_decision(record: IntakeRecord, decision: SenseDecision) -> IntakeRecord:
    return record.model_copy(update={
        "status": "ready" if decision.status == "ready" else "sensing",
        "resolved_dimensions": decision.resolved_dimensions,
        "current_question": decision.next_question,
        "preview": decision.preview,
    })


async def start_intake(
    request: IntakeCreate,
    *,
    store: IntakeStore,
    agent: SensingAgent,
    owner_id: str = "",
    source_snapshot: ArchiveSnapshot | None = None,
) -> IntakeRecord:
    sources = decode_sources(request)
    material_inspection = inspect_materials(MaterialInspectionRequest(
        project_locator=request.project_locator,
        materials=request.materials,
    ))
    record = IntakeRecord(
        intake_id=uuid4().hex,
        project_name=request.project_name,
        goal=request.goal,
        sources=[reference for reference, _ in sources],
        project_locator=request.project_locator,
        material_inspection=material_inspection,
        owner_id=owner_id,
        selected_project_id=request.selected_project_id,
        source_snapshot=source_snapshot,
    )
    store.create(record, sources)
    decision = await agent.assess(
        record,
        [(reference.filename, reference.media_type, data) for reference, data in sources],
    )
    record = apply_decision(record, decision)
    store.update(record)
    return record


async def answer_intake(
    intake_id: str,
    answer: IntakeAnswer,
    *,
    store: IntakeStore,
    agent: SensingAgent,
) -> IntakeRecord:
    record = store.read(intake_id)
    if record.status != "sensing" or record.current_question is None:
        raise ValueError("intake is not waiting for an answer")
    if answer.dimension != record.current_question.dimension:
        raise ValueError("answer does not match the active SixSense question")
    answers = dict(record.answers)
    answers[answer.dimension.value] = answer.answer
    resolved = list(dict.fromkeys([*record.resolved_dimensions, answer.dimension]))
    record = record.model_copy(update={
        "answers": answers,
        "resolved_dimensions": resolved,
        "current_question": None,
    })
    store.update(record)
    decision = await agent.assess(record, source_payloads(store, record))
    record = apply_decision(record, decision)
    store.update(record)
    return record


async def restart_intake(
    intake_id: str,
    revision: IntakeRevision,
    *,
    store: IntakeStore,
    agent: SensingAgent,
) -> IntakeRecord:
    previous = store.read(intake_id)
    if previous.status != "ready" or previous.preview is None:
        raise ValueError("only a completed Outcome Preview can be revised")
    decisions = "\n".join(f"- {key}: {value}" for key, value in previous.answers.items())
    synthesized = (
        f"{previous.goal}\n\nConfirmed discovery decisions:\n{decisions or '- Inferred from the supplied goal and sources.'}"
        f"\n\nRequested revision:\n{revision.change_request}"
    )
    if len(synthesized) > 5000:
        raise ValueError("revised goal exceeds the 5,000 character intake limit")
    copied_sources = [
        (reference, store.source_bytes(previous.intake_id, reference))
        for reference in previous.sources
    ]
    record = IntakeRecord(
        intake_id=uuid4().hex,
        project_name=previous.project_name,
        goal=synthesized,
        sources=list(previous.sources),
        project_locator=previous.project_locator,
        material_inspection=previous.material_inspection,
        owner_id=previous.owner_id,
        selected_project_id=previous.selected_project_id,
        source_snapshot=previous.source_snapshot,
    )
    store.create(record, copied_sources)
    decision = await agent.assess(
        record,
        [(reference.filename, reference.media_type, data) for reference, data in copied_sources],
    )
    record = apply_decision(record, decision)
    store.update(record)
    return record
