"""Receipt-gated execution path owned by the Godot Topology ToolPack."""

from __future__ import annotations

import asyncio
import tempfile
import zipfile
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from khalinos.godot_topology import GodotProjectPlan, compile_godot_topology
from khalinos.models import (
    AgentVerification,
    CriterionFinding,
    QuestReceipt,
    RunRecord,
    RunStatus,
    canonical_sha256,
)
from khalinos.storage import RunStore
from khalinos.toolpacks import ToolPackRegistry
from khalinos.workflow import _enforce_verification_contract, _validate_plan_authority


class GodotTeam(Protocol):
    call_count: int

    async def plan_godot(self, payload: dict) -> GodotProjectPlan: ...

    async def verify_godot(self, payload: dict) -> AgentVerification: ...


def _blocked(criteria: list[str], issues: list[str]) -> AgentVerification:
    detail = "; ".join(issues) or "Godot deterministic verification failed"
    return AgentVerification(
        findings=[
            CriterionFinding(criterion=item, passed=False, evidence=detail)
            for item in criteria
        ],
        verdict="REPAIR",
        repair_instructions=issues or ["Repair the bounded Godot topology plan."],
    )


async def execute_godot_run(
    run_id: str,
    *,
    store: RunStore,
    team: GodotTeam,
    registry: ToolPackRegistry,
) -> RunRecord:
    """Plan once, compile with trusted code, and verify every Quest independently."""

    record = store.read_record(run_id)
    brief = store.read_brief(run_id)
    try:
        binding = brief.toolpack_binding
        if binding is None or binding != record.toolpack_binding:
            raise PermissionError("run and approved brief must carry the same ToolPack binding")
        if canonical_sha256(brief) != record.brief_sha256:
            raise PermissionError("approved brief digest changed after authorization")
        toolpack = registry.resolve(binding)
        if toolpack.manifest.toolpack_id != "godot.topology":
            raise PermissionError("Godot workflow received a non-Godot ToolPack")
        if tuple(sorted(brief.authorized_output_files)) != toolpack.manifest.output.authorized_paths:
            raise PermissionError("approved output files do not match the Godot ToolPack manifest")
        if record.work_mode != "new_product_build" or record.source_snapshot is not None:
            raise PermissionError("Godot Topology ToolPack currently authorizes new products only")

        record = record.model_copy(update={
            "status": RunStatus.PLANNING,
            "message": "Godot Project Owner is issuing a bounded topology Quest chain.",
        })
        store.update(record)
        decision = await team.plan_godot({
            "approved_brief": brief.model_dump(mode="json"),
            "toolpack_manifest": toolpack.manifest.model_dump(mode="json"),
        })
        if decision.topology.project_name != brief.project_name:
            raise PermissionError("Godot Project Owner changed the approved project name")
        if (
            decision.quest_plan.toolpack_binding is not None
            and decision.quest_plan.toolpack_binding != binding
        ):
            raise PermissionError("Godot Project Owner attempted to change the ToolPack binding")
        plan = decision.quest_plan.model_copy(update={"toolpack_binding": binding})
        if len(plan.quests) > brief.max_quests:
            raise PermissionError("Godot Project Owner exceeded the approved Quest limit")
        _validate_plan_authority(brief, plan)
        artifact = compile_godot_topology(decision.topology)
        store.put_json(run_id, "godot/project_plan.json", decision.model_dump(mode="json"))
        store.put_json(run_id, "quest_plan.json", plan.model_dump(mode="json"))
        store.put_json(run_id, "godot/compiled_manifest.json", {
            "plan_sha256": artifact.plan_sha256,
            "bundle_sha256": artifact.bundle_sha256,
            "files": sorted(artifact.files),
            "toolpack_binding": binding.model_dump(mode="json"),
        })

        parent_receipt_id: str | None = None
        receipt_ids: list[str] = []
        for quest in plan.quests:
            record = record.model_copy(update={
                "status": RunStatus.EXECUTING,
                "current_quest_id": quest.quest_id,
                "completed_receipt_ids": receipt_ids,
                "message": f"Trusted Godot materializer is executing {quest.quest_id}.",
                "model_calls": team.call_count,
            })
            store.update(record)
            with tempfile.TemporaryDirectory(prefix=f"khalinos-godot-{run_id}-{quest.quest_id}-") as temporary:
                root = Path(temporary) / "product"
                evidence_dir = Path(temporary) / "evidence"
                toolpack.execution_adapter.materialize(artifact, root)
                record = record.model_copy(update={
                    "status": RunStatus.RUNTIME_CHECKING,
                    "message": f"Digest-bound Godot headless runtime is checking {quest.quest_id}.",
                    "model_calls": team.call_count,
                })
                store.update(record)
                deterministic = await asyncio.to_thread(
                    toolpack.evidence_adapter.verify,
                    artifact,
                    root,
                    evidence_dir,
                    quest.acceptance_criteria,
                )
                for raw_path in sorted(artifact.files):
                    store.put_file(
                        run_id,
                        f"quests/{quest.quest_id}/product/{raw_path}",
                        root / raw_path,
                        "text/plain",
                    )
                for evidence_file in sorted(evidence_dir.glob("*")):
                    if evidence_file.is_file():
                        store.put_file(
                            run_id,
                            f"quests/{quest.quest_id}/evidence/{evidence_file.name}",
                            evidence_file,
                            "application/json",
                        )
                store.put_json(
                    run_id,
                    f"quests/{quest.quest_id}/deterministic_evidence.json",
                    deterministic.model_dump(mode="json"),
                )

            record = record.model_copy(update={
                "status": RunStatus.VERIFYING,
                "message": f"Independent Godot Verifier is checking {quest.quest_id}.",
                "model_calls": team.call_count,
            })
            store.update(record)
            verification = (
                await team.verify_godot({
                    "approved_brief": brief.model_dump(mode="json"),
                    "quest": quest.model_dump(mode="json"),
                    "topology_plan": decision.topology.model_dump(mode="json"),
                    "compiled_artifact": {
                        "plan_sha256": artifact.plan_sha256,
                        "bundle_sha256": artifact.bundle_sha256,
                        "files": sorted(artifact.files),
                    },
                    "deterministic_evidence": deterministic.model_dump(mode="json"),
                })
                if deterministic.passed
                else _blocked(quest.acceptance_criteria, deterministic.issues)
            )
            verification = _enforce_verification_contract(
                quest.acceptance_criteria,
                deterministic.criterion_evidence,
                verification,
            )
            passed = deterministic.passed and verification.verdict == "PASS"
            receipt = QuestReceipt(
                receipt_id=f"QR-{uuid4().hex[:16]}",
                quest_id=quest.quest_id,
                quest_sha256=canonical_sha256(quest),
                parent_receipt_id=parent_receipt_id,
                artifact_sha256=canonical_sha256(artifact),
                toolpack_binding=binding,
                deterministic_evidence=deterministic,
                independent_verification=verification,
                repair_rounds=0,
                state="passed" if passed else "blocked",
            )
            store.put_json(
                run_id,
                f"quests/{quest.quest_id}/receipt.json",
                receipt.model_dump(mode="json"),
            )
            if not passed:
                record = record.model_copy(update={
                    "status": RunStatus.BLOCKED,
                    "message": f"{quest.quest_id} stopped; Godot topology evidence did not pass.",
                    "model_calls": team.call_count,
                })
                store.update(record)
                return record
            receipt_ids.append(receipt.receipt_id)
            parent_receipt_id = receipt.receipt_id

        with tempfile.TemporaryDirectory(prefix=f"khalinos-godot-final-{run_id}-") as temporary:
            archive = Path(temporary) / "source.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
                for raw_path, content in sorted(artifact.files.items()):
                    output.writestr(raw_path, content.encode("utf-8"))
            archive_uri = store.put_file(
                run_id, "final/source.zip", archive, "application/zip"
            )
        store.put_json(run_id, "final/artifact_manifest.json", {
            "artifact_sha256": canonical_sha256(artifact),
            "plan_sha256": artifact.plan_sha256,
            "bundle_sha256": artifact.bundle_sha256,
            "toolpack_binding": binding.model_dump(mode="json"),
            "files": sorted(artifact.files),
            "receipt_ids": receipt_ids,
            "source_archive": archive_uri,
        })
        record = record.model_copy(update={
            "status": RunStatus.PASSED,
            "current_quest_id": None,
            "completed_receipt_ids": receipt_ids,
            "message": "Every Godot topology Quest passed headless checks and independent verification.",
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
