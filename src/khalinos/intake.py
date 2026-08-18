"""SixSense intake state transitions before execution authorization."""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from khalinos.models import (
    IntakeAnswer,
    IntakeCreate,
    IntakeRecord,
    IntakeRevision,
    OutcomePreview,
    SenseDecision,
    SourceReference,
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


async def start_intake(request: IntakeCreate, *, store: IntakeStore, agent: SensingAgent) -> IntakeRecord:
    sources = decode_sources(request)
    record = IntakeRecord(
        intake_id=uuid4().hex,
        project_name=request.project_name,
        goal=request.goal,
        sources=[reference for reference, _ in sources],
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
    )
    store.create(record, copied_sources)
    decision = await agent.assess(
        record,
        [(reference.filename, reference.media_type, data) for reference, data in copied_sources],
    )
    record = apply_decision(record, decision)
    store.update(record)
    return record
