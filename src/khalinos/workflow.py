"""Receipt-gated autonomous Quest execution."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from khalinos.models import (
    AgentVerification,
    ArtifactBundle,
    CriterionFinding,
    QuestPlan,
    QuestReceipt,
    RunRecord,
    RunStatus,
    UserBrief,
    canonical_sha256,
)
from khalinos.storage import RunStore
from khalinos.verification import materialize, verify_bundle


class Team(Protocol):
    call_count: int
    async def plan(self, payload: dict) -> QuestPlan: ...
    async def make(self, payload: dict) -> ArtifactBundle: ...
    async def verify(self, payload: dict) -> AgentVerification: ...
    async def repair(self, payload: dict) -> ArtifactBundle: ...


def _blocked_verification(criteria: list[str], issues: list[str]) -> AgentVerification:
    detail = "; ".join(issues) or "deterministic verification failed"
    return AgentVerification(
        findings=[CriterionFinding(criterion=item, passed=False, evidence=detail) for item in criteria],
        verdict="REPAIR",
        repair_instructions=issues or ["Repair the deterministic runtime failure."],
    )


async def execute_run(run_id: str, *, store: RunStore, team: Team) -> RunRecord:
    record = store.read_record(run_id)
    brief = store.read_brief(run_id)
    try:
        record = record.model_copy(update={"status": RunStatus.PLANNING, "message": "Gemini Project Owner is issuing the Quest chain."})
        store.update(record)
        plan = await team.plan({"approved_brief": brief.model_dump(mode="json")})
        if len(plan.quests) > brief.max_quests:
            raise PermissionError("Project Owner exceeded the approved Quest limit")
        store.put_json(run_id, "quest_plan.json", plan.model_dump(mode="json"))
        current: ArtifactBundle | None = None
        parent_receipt_id: str | None = None
        receipt_ids: list[str] = []
        for quest in plan.quests:
            record = record.model_copy(update={
                "status": RunStatus.EXECUTING,
                "current_quest_id": quest.quest_id,
                "completed_receipt_ids": receipt_ids,
                "message": f"Accountable Maker is executing {quest.quest_id}.",
                "model_calls": team.call_count,
            })
            store.update(record)
            payload = {
                "approved_brief": brief.model_dump(mode="json"),
                "quest": quest.model_dump(mode="json"),
                "previous_verified_bundle": current.model_dump(mode="json") if current else None,
                "parent_receipt_id": parent_receipt_id,
            }
            candidate = await team.make(payload)
            repair_round = 0
            while True:
                with tempfile.TemporaryDirectory(prefix=f"khalinos-{run_id}-{quest.quest_id}-") as temporary:
                    root = Path(temporary) / "product"
                    evidence_dir = Path(temporary) / "evidence"
                    materialize(candidate, root)
                    # Playwright's synchronous API must not run on the worker's
                    # asyncio event-loop thread. Keep deterministic verification
                    # isolated from the agent runtime and await its result.
                    deterministic = await asyncio.to_thread(
                        verify_bundle, candidate, root, evidence_dir
                    )
                    for file in candidate.files:
                        store.put_file(run_id, f"quests/{quest.quest_id}/r{repair_round}/product/{file.path}", root / file.path, "text/plain")
                    for screenshot in evidence_dir.glob("*.png"):
                        store.put_file(run_id, f"quests/{quest.quest_id}/r{repair_round}/evidence/{screenshot.name}", screenshot, "image/png")
                record = record.model_copy(update={
                    "status": RunStatus.VERIFYING,
                    "message": f"Independent Verifier is checking {quest.quest_id} revision {repair_round}.",
                    "model_calls": team.call_count,
                })
                store.update(record)
                verification = (
                    await team.verify({
                        "approved_brief": brief.model_dump(mode="json"),
                        "quest": quest.model_dump(mode="json"),
                        "artifact": candidate.model_dump(mode="json"),
                        "deterministic_evidence": deterministic.model_dump(mode="json"),
                    })
                    if deterministic.passed
                    else _blocked_verification(quest.acceptance_criteria, deterministic.issues)
                )
                passed = deterministic.passed and verification.verdict == "PASS"
                if passed or repair_round >= brief.max_repairs_per_quest:
                    receipt = QuestReceipt(
                        receipt_id=f"QR-{uuid4().hex[:16]}",
                        quest_id=quest.quest_id,
                        quest_sha256=canonical_sha256(quest),
                        parent_receipt_id=parent_receipt_id,
                        artifact_sha256=canonical_sha256(candidate),
                        deterministic_evidence=deterministic,
                        independent_verification=verification,
                        repair_rounds=repair_round,
                        state="passed" if passed else "blocked",
                    )
                    store.put_json(run_id, f"quests/{quest.quest_id}/receipt.json", receipt.model_dump(mode="json"))
                    if not passed:
                        record = record.model_copy(update={
                            "status": RunStatus.BLOCKED,
                            "message": f"{quest.quest_id} stopped after the approved repair limit.",
                            "model_calls": team.call_count,
                        })
                        store.update(record)
                        return record
                    parent_receipt_id = receipt.receipt_id
                    receipt_ids.append(receipt.receipt_id)
                    current = candidate
                    break
                repair_round += 1
                record = record.model_copy(update={
                    "status": RunStatus.REPAIRING,
                    "message": f"Technical Repair Agent is repairing {quest.quest_id} revision {repair_round}.",
                    "model_calls": team.call_count,
                })
                store.update(record)
                candidate = await team.repair({
                    **payload,
                    "failed_bundle": candidate.model_dump(mode="json"),
                    "deterministic_evidence": deterministic.model_dump(mode="json"),
                    "independent_verification": verification.model_dump(mode="json"),
                    "repair_round": repair_round,
                })
        if current is None:
            raise RuntimeError("Project Owner produced no executable Quest")
        store.put_json(run_id, "final/artifact_manifest.json", {
            "artifact_sha256": canonical_sha256(current),
            "files": [item.path for item in current.files],
            "receipt_ids": receipt_ids,
        })
        record = record.model_copy(update={
            "status": RunStatus.PASSED,
            "current_quest_id": None,
            "completed_receipt_ids": receipt_ids,
            "message": "Every Quest passed deterministic runtime checks and independent verification.",
            "model_calls": team.call_count,
        })
        store.update(record)
        return record
    except Exception as exc:
        record = record.model_copy(update={
            "status": RunStatus.FAILED,
            "message": f"{type(exc).__name__}: {exc}"[:1000],
            "model_calls": team.call_count,
        })
        store.update(record)
        return record
