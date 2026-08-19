"""Receipt-gated workflow for the Godot Gameplay Vertical Slice ToolPack."""

from __future__ import annotations

import asyncio
import tempfile
import zipfile
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from khalinos.godot_gameplay import GodotGameplayProjectPlan, compile_godot_gameplay
from khalinos.models import (
    AgentVerification, ArtifactAsset, CriterionFinding, QuestReceipt, RunRecord, RunStatus,
    UserBrief, VisualAssetGate, VisualConcept, VisualConceptPlan, VisualSelection,
    VisualSelectionReceipt, canonical_sha256,
)
from khalinos.projects import ProjectStore
from khalinos.storage import RunStore
from khalinos.toolpacks import ToolPackRegistry
from khalinos.workflow import _enforce_verification_contract, _validate_plan_authority


class GodotGameplayTeam(Protocol):
    call_count: int
    async def plan_godot_gameplay(self, payload: dict) -> GodotGameplayProjectPlan: ...
    async def plan_visuals(self, payload: dict) -> VisualConceptPlan: ...
    async def make_visual_asset(self, brief: UserBrief, concept: VisualConcept) -> ArtifactAsset: ...
    async def verify_visual_asset(self, candidate_id: str, asset: ArtifactAsset, concept: VisualConcept) -> VisualAssetGate: ...
    async def select_visual(self, payload: dict, screenshots: list[tuple[str, bytes]]) -> VisualSelection: ...
    async def verify_godot(self, payload: dict) -> AgentVerification: ...


def _blocked(criteria: list[str], issues: list[str]) -> AgentVerification:
    detail = "; ".join(issues) or "Godot gameplay verification failed"
    return AgentVerification(
        findings=[CriterionFinding(criterion=item, passed=False, evidence=detail) for item in criteria],
        verdict="REPAIR",
        repair_instructions=issues or ["Repair the bounded Godot gameplay plan."],
    )


async def execute_godot_gameplay_run(
    run_id: str,
    *,
    store: RunStore,
    team: GodotGameplayTeam,
    registry: ToolPackRegistry,
    project_store: ProjectStore | None = None,
) -> RunRecord:
    record = store.read_record(run_id)
    brief = store.read_brief(run_id)
    try:
        binding = brief.toolpack_binding
        if binding is None or binding != record.toolpack_binding:
            raise PermissionError("run and approved brief must carry the same ToolPack binding")
        if canonical_sha256(brief) != record.brief_sha256:
            raise PermissionError("approved brief digest changed after authorization")
        toolpack = registry.resolve(binding)
        if toolpack.manifest.toolpack_id != "godot.gameplay":
            raise PermissionError("Godot gameplay workflow received the wrong ToolPack")
        if tuple(sorted(brief.authorized_output_files)) != toolpack.manifest.output.authorized_paths:
            raise PermissionError("approved output files do not match the Godot gameplay ToolPack manifest")
        if record.work_mode != "new_product_build" or record.source_snapshot is not None:
            raise PermissionError("Godot Gameplay ToolPack authorizes new products only")

        record = record.model_copy(update={
            "status": RunStatus.PLANNING,
            "message": "Godot Project Owner is binding a gameplay vertical-slice Quest chain.",
        })
        store.update(record)
        decision = await team.plan_godot_gameplay({
            "approved_brief": brief.model_dump(mode="json"),
            "toolpack_manifest": toolpack.manifest.model_dump(mode="json"),
        })
        if decision.gameplay.project_name != brief.project_name:
            raise PermissionError("Godot Project Owner changed the approved project name")
        plan = decision.quest_plan.model_copy(update={"toolpack_binding": binding})
        if len(plan.quests) > brief.max_quests:
            raise PermissionError("Godot Project Owner exceeded the approved Quest limit")
        _validate_plan_authority(brief, plan)
        store.put_json(run_id, "godot/gameplay_project_plan.json", decision.model_dump(mode="json"))
        store.put_json(run_id, "quest_plan.json", plan.model_dump(mode="json"))

        record = record.model_copy(update={
            "status": RunStatus.VISUALIZING,
            "message": "Visual Director is issuing three gameplay-ready visual foundations.",
            "model_calls": team.call_count,
        })
        store.update(record)
        visual_plan = await team.plan_visuals({
            "approved_brief": brief.model_dump(mode="json"),
            "quest_plan_summary": plan.model_dump(mode="json"),
            "gameplay_plan": decision.gameplay.model_dump(mode="json"),
            "render_surface": "Godot 4.7.1 2D gameplay at the approved viewport",
        })
        store.put_json(run_id, "visuals/concept_plan.json", visual_plan.model_dump(mode="json"))

        eligible: dict[str, tuple[object, object]] = {}
        screenshots: list[tuple[str, bytes]] = []
        screenshot_paths: dict[str, str] = {}
        asset_digests: dict[str, str] = {}
        evidence_payload: dict[str, dict] = {}
        for concept in visual_plan.candidates:
            record = record.model_copy(update={
                "status": RunStatus.VISUALIZING,
                "message": f"Nano Banana is generating gameplay candidate {concept.candidate_id}: {concept.name}.",
                "model_calls": team.call_count,
            })
            store.update(record)
            asset = await team.make_visual_asset(brief, concept)
            asset_digests[concept.candidate_id] = asset.sha256
            store.put_bytes(run_id, f"visuals/{concept.candidate_id}/asset/{asset.path}", asset.bytes(), asset.media_type)
            gate = await team.verify_visual_asset(concept.candidate_id, asset, concept)
            store.put_json(run_id, f"visuals/{concept.candidate_id}/asset_gate.json", gate.model_dump(mode="json"))
            if not gate.approved:
                evidence_payload[concept.candidate_id] = {"passed": False, "issues": gate.issues}
                continue
            artifact = compile_godot_gameplay(decision.gameplay, concept, asset)
            with tempfile.TemporaryDirectory(prefix=f"khalinos-gameplay-{run_id}-{concept.candidate_id}-") as temporary:
                root = Path(temporary) / "product"
                evidence_dir = Path(temporary) / "evidence"
                toolpack.execution_adapter.materialize(artifact, root)
                deterministic = await asyncio.to_thread(
                    toolpack.evidence_adapter.verify,
                    artifact,
                    root,
                    evidence_dir,
                    brief.acceptance_criteria,
                )
                for raw_path in sorted(artifact.files):
                    store.put_file(run_id, f"visuals/{concept.candidate_id}/product/{raw_path}", root / raw_path, "text/plain")
                store.put_file(run_id, f"visuals/{concept.candidate_id}/product/{asset.path}", root / asset.path, asset.media_type)
                for evidence_file in sorted(evidence_dir.iterdir()):
                    if not evidence_file.is_file() or evidence_file.suffix not in {".json", ".png"}:
                        continue
                    media_type = "image/png" if evidence_file.suffix == ".png" else "application/json"
                    uri = store.put_file(run_id, f"visuals/{concept.candidate_id}/evidence/{evidence_file.name}", evidence_file, media_type)
                    if evidence_file.name in deterministic.screenshot_names:
                        screenshot_paths[concept.candidate_id] = uri
                        screenshots.append((concept.candidate_id, evidence_file.read_bytes()))
            evidence_payload[concept.candidate_id] = deterministic.model_dump(mode="json")
            store.put_json(run_id, f"visuals/{concept.candidate_id}/deterministic_evidence.json", deterministic.model_dump(mode="json"))
            if deterministic.passed and concept.candidate_id in screenshot_paths:
                eligible[concept.candidate_id] = (artifact, deterministic)

        if len(eligible) < 2:
            raise RuntimeError("fewer than two Godot gameplay candidates passed real mechanics and rendering")
        record = record.model_copy(update={
            "status": RunStatus.VISUAL_SELECTING,
            "message": "Independent Visual Verifier is comparing real Godot gameplay renders.",
            "model_calls": team.call_count,
        })
        store.update(record)
        selection = await team.select_visual(
            {
                "approved_brief": brief.model_dump(mode="json"),
                "visual_concept_plan": visual_plan.model_dump(mode="json"),
                "render_surface": "real Godot gameplay PNG",
                "eligible_candidate_ids": list(eligible),
                "deterministic_evidence": evidence_payload,
            },
            [item for item in screenshots if item[0] in eligible],
        )
        assessed = [item.candidate_id for item in selection.assessments]
        if assessed != list(eligible) or selection.selected_candidate_id not in eligible:
            raise ValueError("Visual Verifier must assess and select exactly the eligible gameplay candidates")
        artifact, deterministic = eligible[selection.selected_candidate_id]
        visual_receipt = VisualSelectionReceipt(
            receipt_id=f"VS-{uuid4().hex[:16]}",
            plan_sha256=canonical_sha256(visual_plan),
            selected_candidate_id=selection.selected_candidate_id,
            selected_artifact_sha256=canonical_sha256(artifact),
            eligible_candidate_ids=list(eligible),
            screenshot_paths={key: value for key, value in screenshot_paths.items() if key in eligible},
            asset_sha256_by_candidate={key: value for key, value in asset_digests.items() if key in eligible},
            selection=selection,
        )
        store.put_json(run_id, "visuals/selection_receipt.json", visual_receipt.model_dump(mode="json"))

        parent_receipt_id: str | None = visual_receipt.receipt_id
        receipt_ids = [visual_receipt.receipt_id]
        for quest in plan.quests:
            record = record.model_copy(update={
                "status": RunStatus.VERIFYING,
                "current_quest_id": quest.quest_id,
                "completed_receipt_ids": receipt_ids,
                "message": f"Independent Godot Verifier is checking gameplay Quest {quest.quest_id}.",
                "model_calls": team.call_count,
            })
            store.update(record)
            verification = await team.verify_godot({
                "approved_brief": brief.model_dump(mode="json"),
                "quest": quest.model_dump(mode="json"),
                "gameplay_plan": decision.gameplay.model_dump(mode="json"),
                "visual_concept": artifact.concept.model_dump(mode="json"),
                "compiled_artifact": {
                    "plan_sha256": artifact.plan_sha256,
                    "bundle_sha256": artifact.bundle_sha256,
                    "files": sorted(artifact.files),
                    "asset_sha256": artifact.asset.sha256,
                },
                "deterministic_evidence": deterministic.model_dump(mode="json"),
            }) if deterministic.passed else _blocked(quest.acceptance_criteria, deterministic.issues)
            verification = _enforce_verification_contract(
                quest.acceptance_criteria, deterministic.criterion_evidence, verification,
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
            store.put_json(run_id, f"quests/{quest.quest_id}/receipt.json", receipt.model_dump(mode="json"))
            if not passed:
                record = record.model_copy(update={
                    "status": RunStatus.BLOCKED,
                    "message": f"{quest.quest_id} stopped; Godot gameplay evidence did not pass.",
                    "model_calls": team.call_count,
                })
                store.update(record)
                return record
            receipt_ids.append(receipt.receipt_id)
            parent_receipt_id = receipt.receipt_id

        with tempfile.TemporaryDirectory(prefix=f"khalinos-gameplay-final-{run_id}-") as temporary:
            archive = Path(temporary) / "source.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
                for raw_path, content in sorted(artifact.files.items()):
                    output.writestr(raw_path, content.encode("utf-8"))
                output.writestr(artifact.asset.path, artifact.asset.bytes())
            archive_uri = store.put_file(run_id, "final/source.zip", archive, "application/zip")
        store.put_json(run_id, "final/artifact_manifest.json", {
            "artifact_sha256": canonical_sha256(artifact),
            "plan_sha256": artifact.plan_sha256,
            "bundle_sha256": artifact.bundle_sha256,
            "asset_sha256": artifact.asset.sha256,
            "toolpack_binding": binding.model_dump(mode="json"),
            "files": sorted([*artifact.files, artifact.asset.path]),
            "receipt_ids": receipt_ids,
            "source_archive": archive_uri,
        })
        record = record.model_copy(update={
            "status": RunStatus.PASSED,
            "current_quest_id": None,
            "completed_receipt_ids": receipt_ids,
            "message": "Godot gameplay vertical slice passed real mechanics, rendering, and independent verification.",
            "model_calls": team.call_count,
        })
        store.update(record)
        if project_store is not None and record.project_id and record.owner_id:
            project = project_store.read_owned(record.project_id, record.owner_id)
            project_store.prepare(project.model_copy(update={
                "latest_run_id": record.run_id,
                "latest_status": RunStatus.PASSED,
                "latest_checkpoint_sha256": canonical_sha256(artifact),
                "latest_receipt_ids": receipt_ids,
            }))
        return record
    except Exception as exc:
        record = record.model_copy(update={
            "status": RunStatus.FAILED,
            "message": f"{type(exc).__name__}: {exc}"[:1000],
            "model_calls": team.call_count,
        })
        store.update(record)
        return record
