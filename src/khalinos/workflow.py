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
    VisualConceptPlan,
    VisualSelection,
    VisualSelectionReceipt,
    canonical_sha256,
)
from khalinos.storage import RunStore
from khalinos.projects import ProjectStore
from khalinos.verification import materialize, verify_bundle


class Team(Protocol):
    call_count: int
    async def plan(self, payload: dict) -> QuestPlan: ...
    async def make(self, payload: dict) -> ArtifactBundle: ...
    async def verify(self, payload: dict) -> AgentVerification: ...
    async def repair(self, payload: dict) -> ArtifactBundle: ...
    async def plan_visuals(self, payload: dict) -> VisualConceptPlan: ...
    async def make_visual(self, payload: dict) -> ArtifactBundle: ...
    async def select_visual(self, payload: dict, screenshots: list[tuple[str, bytes]]) -> VisualSelection: ...


def _blocked_verification(criteria: list[str], issues: list[str]) -> AgentVerification:
    detail = "; ".join(issues) or "deterministic verification failed"
    return AgentVerification(
        findings=[CriterionFinding(criterion=item, passed=False, evidence=detail) for item in criteria],
        verdict="REPAIR",
        repair_instructions=issues or ["Repair the deterministic runtime failure."],
    )


def _enforce_verification_contract(
    criteria: list[str],
    criterion_evidence: dict[str, list[str]],
    verification: AgentVerification,
) -> AgentVerification:
    if len(verification.findings) != len(criteria):
        return _blocked_verification(
            criteria,
            ["Independent Verifier must return exactly one finding for every active acceptance criterion."],
        )
    missing_runtime = [criterion for criterion in criteria if not criterion_evidence.get(criterion)]
    if missing_runtime:
        return _blocked_verification(
            criteria,
            ["Runtime-observable criteria lack typed assertion evidence: " + " | ".join(missing_runtime)],
        )
    return AgentVerification(
        findings=[
            CriterionFinding(
                criterion=criterion,
                passed=finding.passed,
                evidence=finding.evidence,
            )
            for criterion, finding in zip(criteria, verification.findings, strict=True)
        ],
        verdict=verification.verdict,
        repair_instructions=verification.repair_instructions,
    )


def _validate_plan_authority(brief: UserBrief, plan: QuestPlan) -> None:
    approved = set(brief.acceptance_criteria)
    planned = {
        criterion
        for quest in plan.quests
        for criterion in quest.acceptance_criteria
    }
    if planned != approved:
        invented = sorted(planned - approved)
        missing = sorted(approved - planned)
        details: list[str] = []
        if invented:
            details.append("invented criteria: " + " | ".join(invented))
        if missing:
            details.append("missing approved criteria: " + " | ".join(missing))
        raise PermissionError(
            "Project Owner acceptance criteria must exactly preserve the approved brief; "
            + "; ".join(details)
        )


async def _select_visual_foundation(
    run_id: str,
    *,
    record: RunRecord,
    brief: UserBrief,
    plan: QuestPlan,
    store: RunStore,
    team: Team,
) -> tuple[ArtifactBundle, VisualSelectionReceipt, RunRecord]:
    record = record.model_copy(update={
        "status": RunStatus.VISUALIZING,
        "message": "Visual Director is issuing three distinct visual concepts.",
        "model_calls": team.call_count,
    })
    store.update(record)
    visual_plan = await team.plan_visuals({
        "approved_brief": brief.model_dump(mode="json"),
        "quest_plan_summary": plan.model_dump(mode="json"),
    })
    store.put_json(run_id, "visuals/concept_plan.json", visual_plan.model_dump(mode="json"))

    eligible: dict[str, ArtifactBundle] = {}
    evidence_by_candidate: dict[str, dict] = {}
    screenshot_payloads: list[tuple[str, bytes]] = []
    screenshot_paths: dict[str, str] = {}
    for concept in visual_plan.candidates:
        record = record.model_copy(update={
            "status": RunStatus.VISUALIZING,
            "message": f"Visual Candidate Maker is rendering {concept.candidate_id}: {concept.name}.",
            "model_calls": team.call_count,
        })
        store.update(record)
        candidate = await team.make_visual({
            "approved_brief": brief.model_dump(mode="json"),
            "shared_visual_contract": visual_plan.shared_contract,
            "visual_concept": concept.model_dump(mode="json"),
        })
        with tempfile.TemporaryDirectory(prefix=f"khalinos-{run_id}-{concept.candidate_id}-") as temporary:
            root = Path(temporary) / "product"
            evidence_dir = Path(temporary) / "evidence"
            materialize(candidate, root)
            deterministic = await asyncio.to_thread(verify_bundle, candidate, root, evidence_dir)
            for file in candidate.files:
                store.put_file(run_id, f"visuals/{concept.candidate_id}/product/{file.path}", root / file.path, "text/plain")
            screenshots = sorted(evidence_dir.glob("*.png"))
            for index, screenshot in enumerate(screenshots, start=1):
                path = store.put_file(
                    run_id,
                    f"visuals/{concept.candidate_id}/evidence/{screenshot.name}",
                    screenshot,
                    "image/png",
                )
                if index == 1:
                    screenshot_paths[concept.candidate_id] = path
                    screenshot_payloads.append((concept.candidate_id, screenshot.read_bytes()))
        evidence_by_candidate[concept.candidate_id] = deterministic.model_dump(mode="json")
        store.put_json(
            run_id,
            f"visuals/{concept.candidate_id}/deterministic_evidence.json",
            deterministic.model_dump(mode="json"),
        )
        if deterministic.passed and concept.candidate_id in screenshot_paths:
            eligible[concept.candidate_id] = candidate

    if len(eligible) < 2:
        raise RuntimeError("fewer than two visual candidates passed deterministic rendering")
    eligible_screenshots = [item for item in screenshot_payloads if item[0] in eligible]
    record = record.model_copy(update={
        "status": RunStatus.VISUAL_SELECTING,
        "message": "Independent Visual Verifier is comparing rendered candidates.",
        "model_calls": team.call_count,
    })
    store.update(record)
    selection = await team.select_visual(
        {
            "approved_brief": brief.model_dump(mode="json"),
            "visual_concept_plan": visual_plan.model_dump(mode="json"),
            "eligible_candidate_ids": list(eligible),
            "deterministic_evidence": evidence_by_candidate,
        },
        eligible_screenshots,
    )
    assessed_ids = [item.candidate_id for item in selection.assessments]
    if assessed_ids != list(eligible):
        raise ValueError("Visual Verifier must assess exactly the eligible candidates")
    if selection.selected_candidate_id not in eligible:
        raise ValueError("Visual Verifier selected an ineligible candidate")
    selected = eligible[selection.selected_candidate_id]
    receipt = VisualSelectionReceipt(
        receipt_id=f"VS-{uuid4().hex[:16]}",
        plan_sha256=canonical_sha256(visual_plan),
        selected_candidate_id=selection.selected_candidate_id,
        selected_artifact_sha256=canonical_sha256(selected),
        eligible_candidate_ids=list(eligible),
        screenshot_paths={key: value for key, value in screenshot_paths.items() if key in eligible},
        selection=selection,
    )
    store.put_json(run_id, "visuals/selection_receipt.json", receipt.model_dump(mode="json"))
    return selected, receipt, record


async def execute_run(
    run_id: str,
    *,
    store: RunStore,
    team: Team,
    project_store: ProjectStore | None = None,
) -> RunRecord:
    record = store.read_record(run_id)
    brief = store.read_brief(run_id)
    try:
        record = record.model_copy(update={"status": RunStatus.PLANNING, "message": "Gemini Project Owner is issuing the Quest chain."})
        store.update(record)
        plan = await team.plan({"approved_brief": brief.model_dump(mode="json")})
        if len(plan.quests) > brief.max_quests:
            raise PermissionError("Project Owner exceeded the approved Quest limit")
        _validate_plan_authority(brief, plan)
        store.put_json(run_id, "quest_plan.json", plan.model_dump(mode="json"))
        existing_repair = record.work_mode == "existing_project_repair"
        if existing_repair:
            if record.source_snapshot is None:
                raise ValueError("existing-project repair requires an immutable source snapshot")
            current = store.read_bundle_archive(record.source_snapshot)
            source_receipt_id = f"SR-{record.source_snapshot.sha256[:16]}"
            store.put_json(run_id, "source/receipt.json", {
                "receipt_id": source_receipt_id,
                "snapshot": record.source_snapshot.model_dump(mode="json"),
                "artifact_sha256": canonical_sha256(current),
                "admission": "validated bounded browser source archive",
            })
            parent_receipt_id: str | None = source_receipt_id
            receipt_ids: list[str] = [source_receipt_id]
        else:
            current, visual_receipt, record = await _select_visual_foundation(
                run_id,
                record=record,
                brief=brief,
                plan=plan,
                store=store,
                team=team,
            )
            parent_receipt_id = visual_receipt.receipt_id
            receipt_ids = [visual_receipt.receipt_id]
        for quest in plan.quests:
            record = record.model_copy(update={
                "status": RunStatus.EXECUTING,
                "current_quest_id": quest.quest_id,
                "completed_receipt_ids": receipt_ids,
                "message": (
                    f"Technical Repair Agent is applying {quest.quest_id} to the verified project snapshot."
                    if existing_repair else f"Accountable Maker is executing {quest.quest_id}."
                ),
                "model_calls": team.call_count,
            })
            store.update(record)
            payload = {
                "approved_brief": brief.model_dump(mode="json"),
                "quest": quest.model_dump(mode="json"),
                "previous_verified_bundle": current.model_dump(mode="json") if current else None,
                "parent_receipt_id": parent_receipt_id,
            }
            candidate = (
                await team.repair({
                    **payload,
                    "failed_bundle": current.model_dump(mode="json"),
                    "deterministic_evidence": {"passed": True, "checks": {"source_admission": True}, "issues": []},
                    "independent_verification": {
                        "verdict": "REPAIR",
                        "repair_instructions": [quest.objective],
                        "findings": [],
                    },
                    "repair_round": 0,
                    "existing_project_entry": True,
                })
                if existing_repair else await team.make(payload)
            )
            repair_round = 0
            while True:
                record = record.model_copy(update={
                    "status": RunStatus.RUNTIME_CHECKING,
                    "message": f"Deterministic runtime is checking {quest.quest_id} revision {repair_round}.",
                    "model_calls": team.call_count,
                })
                store.update(record)
                with tempfile.TemporaryDirectory(prefix=f"khalinos-{run_id}-{quest.quest_id}-") as temporary:
                    root = Path(temporary) / "product"
                    evidence_dir = Path(temporary) / "evidence"
                    materialize(candidate, root)
                    # Playwright's synchronous API must not run on the worker's
                    # asyncio event-loop thread. Keep deterministic verification
                    # isolated from the agent runtime and await its result.
                    deterministic = await asyncio.to_thread(
                        verify_bundle,
                        candidate,
                        root,
                        evidence_dir,
                        quest.acceptance_criteria,
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
                        "criterion_evidence": deterministic.criterion_evidence,
                    })
                    if deterministic.passed
                    else _blocked_verification(quest.acceptance_criteria, deterministic.issues)
                )
                verification = _enforce_verification_contract(
                    quest.acceptance_criteria,
                    deterministic.criterion_evidence,
                    verification,
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
        source_snapshot = store.put_bundle_archive(run_id, current)
        store.put_json(run_id, "final/artifact_manifest.json", {
            "artifact_sha256": canonical_sha256(current),
            "files": [item.path for item in current.files],
            "receipt_ids": receipt_ids,
            "source_snapshot": source_snapshot.model_dump(mode="json"),
        })
        record = record.model_copy(update={
            "status": RunStatus.PASSED,
            "current_quest_id": None,
            "completed_receipt_ids": receipt_ids,
            "message": "Every Quest passed deterministic runtime checks and independent verification.",
            "model_calls": team.call_count,
        })
        store.update(record)
        if project_store is not None and record.project_id and record.owner_id:
            project_store.update_checkpoint(record, canonical_sha256(current), source_snapshot)
        return record
    except Exception as exc:
        record = record.model_copy(update={
            "status": RunStatus.FAILED,
            "message": f"{type(exc).__name__}: {exc}"[:1000],
            "model_calls": team.call_count,
        })
        store.update(record)
        return record
