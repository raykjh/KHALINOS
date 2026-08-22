"""Receipt-gated workflow for the Godot Gameplay Vertical Slice ToolPack."""

from __future__ import annotations

import asyncio
import tempfile
import zipfile
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from khalinos.agent_capability_receipts import build_agent_capability_trace
from khalinos.godot_gameplay import (
    GODOT_GAMEPLAY_SPRITE_PROFILE,
    GodotGameplayProjectPlan,
    compile_godot_gameplay,
    compose_godot_gameplay_capabilities,
    derive_sprite_atlas_plan,
    validate_gameplay_plan_requirements,
)
from khalinos.models import (
    AgentVerification, ArtifactAsset, CriterionFinding, QuestReceipt, RunRecord, RunStatus,
    SpriteAtlasGate, UserBrief, VisualAssetGate, VisualConcept, VisualConceptPlan, VisualSelection,
    VisualSelectionReceipt, canonical_sha256,
)
from khalinos.projects import ProjectStore
from khalinos.storage import RunStore
from khalinos.toolpacks import ToolPackRegistry
from khalinos.sprite_assets import SPRITE_SEGMENTATION_CONTRACT, SpriteAtlasPlan
from khalinos.workflow import _bind_plan_authority, _enforce_verification_contract


class GodotGameplayTeam(Protocol):
    call_count: int
    call_count_by_agent: dict[str, int]
    async def plan_godot_gameplay(self, payload: dict) -> GodotGameplayProjectPlan: ...
    async def plan_visuals(self, payload: dict) -> VisualConceptPlan: ...
    async def make_visual_asset(self, brief: UserBrief, concept: VisualConcept, feedback: tuple[str, ...] = ()) -> ArtifactAsset: ...
    async def verify_visual_asset(self, candidate_id: str, asset: ArtifactAsset, concept: VisualConcept) -> VisualAssetGate: ...
    async def make_sprite_atlas(self, brief: UserBrief, concept: VisualConcept, plan: SpriteAtlasPlan, feedback: tuple[str, ...] = ()) -> ArtifactAsset: ...
    async def verify_sprite_atlas(self, plan: SpriteAtlasPlan, asset: ArtifactAsset, concept: VisualConcept) -> SpriteAtlasGate: ...
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
        segmentation_dependencies = [
            item for item in toolpack.manifest.external_dependencies
            if item.dependency_id == "isnet-anime.onnx"
        ]
        if len(segmentation_dependencies) != 1:
            raise PermissionError("Godot Gameplay ToolPack is missing one exact sprite segmentation dependency")
        dependency = segmentation_dependencies[0]
        if (
            dependency.sha256 != SPRITE_SEGMENTATION_CONTRACT.model_sha256
            or dependency.byte_size != SPRITE_SEGMENTATION_CONTRACT.model_bytes
            or dependency.version != SPRITE_SEGMENTATION_CONTRACT.model_version
        ):
            raise PermissionError("sprite segmentation dependency does not match the approved local contract")
        store.put_json(run_id, "sprites/segmentation_contract.json", {
            **SPRITE_SEGMENTATION_CONTRACT.model_dump(mode="json"),
            "contract_sha256": SPRITE_SEGMENTATION_CONTRACT.sha256(),
        })

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
        validate_gameplay_plan_requirements(decision.gameplay, brief.acceptance_criteria)
        plan = _bind_plan_authority(
            brief,
            decision.quest_plan.model_copy(update={"toolpack_binding": binding}),
        )
        if len(plan.quests) > brief.max_quests:
            raise PermissionError("Godot Project Owner exceeded the approved Quest limit")
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
                store.put_bytes(
                    run_id, f"visuals/{concept.candidate_id}/repair/attempt-0/{asset.path}",
                    asset.bytes(), asset.media_type,
                )
                store.put_json(
                    run_id, f"visuals/{concept.candidate_id}/repair/attempt-0/asset_gate.json",
                    gate.model_dump(mode="json"),
                )
                asset = await team.make_visual_asset(brief, concept, tuple(gate.issues))
                asset_digests[concept.candidate_id] = asset.sha256
                store.put_bytes(run_id, f"visuals/{concept.candidate_id}/asset/{asset.path}", asset.bytes(), asset.media_type)
                gate = await team.verify_visual_asset(concept.candidate_id, asset, concept)
                store.put_json(run_id, f"visuals/{concept.candidate_id}/asset_gate.json", gate.model_dump(mode="json"))
            if not gate.approved:
                evidence_payload[concept.candidate_id] = {"passed": False, "issues": gate.issues}
                continue
            record = record.model_copy(update={
                "status": RunStatus.EXECUTING,
                "message": f"Trusted Accountable Maker is composing gameplay candidate {concept.candidate_id} from the bound Capability Packs.",
                "model_calls": team.call_count,
            })
            store.update(record)
            artifact = compile_godot_gameplay(decision.gameplay, concept, asset)
            with tempfile.TemporaryDirectory(prefix=f"khalinos-gameplay-{run_id}-{concept.candidate_id}-") as temporary:
                root = Path(temporary) / "product"
                evidence_dir = Path(temporary) / "evidence"
                toolpack.execution_adapter.materialize(artifact, root)
                record = record.model_copy(update={
                    "status": RunStatus.RUNTIME_CHECKING,
                    "message": f"Deterministic Runtime is checking real mechanics and rendering for gameplay candidate {concept.candidate_id}.",
                    "model_calls": team.call_count,
                })
                store.update(record)
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

        sprite_plan = derive_sprite_atlas_plan(decision.gameplay)
        store.put_json(run_id, "sprites/plan.json", sprite_plan.model_dump(mode="json"))
        record = record.model_copy(update={
            "status": RunStatus.VISUALIZING,
            "message": "Nano Banana is generating isolated character sources for trusted atlas composition.",
            "model_calls": team.call_count,
        })
        store.update(record)
        try:
            sprite_atlas = await team.make_sprite_atlas(brief, artifact.concept, sprite_plan)
        except Exception as exc:
            store.put_json(run_id, "sprites/generation_failure.json", {
                "issues": [f"{type(exc).__name__}: {exc}"],
            })
            raise RuntimeError("an isolated sprite source failed its bounded normalization") from exc
        store.put_bytes(run_id, f"sprites/attempts/1/{sprite_atlas.path}", sprite_atlas.bytes(), sprite_atlas.media_type)
        sprite_gate = await team.verify_sprite_atlas(sprite_plan, sprite_atlas, artifact.concept)
        store.put_json(run_id, "sprites/attempts/1/gate.json", sprite_gate.model_dump(mode="json"))
        if not sprite_gate.approved:
            record = record.model_copy(update={
                "status": RunStatus.VISUALIZING,
                "message": "Sprite Atlas Gate requested one bounded whole-atlas refinement.",
                "model_calls": team.call_count,
            })
            store.update(record)
            try:
                sprite_atlas = await team.make_sprite_atlas(
                    brief,
                    artifact.concept,
                    sprite_plan,
                    tuple(sprite_gate.issues),
                )
            except Exception as exc:
                store.put_json(run_id, "sprites/generation_failure.json", {
                    "attempt": 2,
                    "issues": [f"{type(exc).__name__}: {exc}"],
                })
                raise RuntimeError("the one bounded sprite-atlas refinement failed normalization") from exc
            store.put_bytes(run_id, f"sprites/attempts/2/{sprite_atlas.path}", sprite_atlas.bytes(), sprite_atlas.media_type)
            sprite_gate = await team.verify_sprite_atlas(sprite_plan, sprite_atlas, artifact.concept)
            store.put_json(run_id, "sprites/attempts/2/gate.json", sprite_gate.model_dump(mode="json"))
        if not sprite_gate.approved:
            raise RuntimeError("the deterministically composed sprite atlas failed its independent semantic gate")
        store.put_bytes(run_id, f"sprites/composed/{sprite_atlas.path}", sprite_atlas.bytes(), sprite_atlas.media_type)
        store.put_json(run_id, "sprites/composed/gate.json", sprite_gate.model_dump(mode="json"))

        record = record.model_copy(update={
            "status": RunStatus.EXECUTING,
            "message": "Trusted Accountable Maker is binding the approved sprite atlas into the final gameplay artifact.",
            "model_calls": team.call_count,
        })
        store.update(record)
        artifact = compile_godot_gameplay(
            decision.gameplay,
            artifact.concept,
            artifact.asset,
            sprite_plan,
            sprite_atlas,
            require_sprite_atlas=True,
        )
        with tempfile.TemporaryDirectory(prefix=f"khalinos-gameplay-final-proof-{run_id}-") as temporary:
            root = Path(temporary) / "product"
            evidence_dir = Path(temporary) / "evidence"
            toolpack.execution_adapter.materialize(artifact, root)
            record = record.model_copy(update={
                "status": RunStatus.RUNTIME_CHECKING,
                "message": "Deterministic Runtime is checking the final sprite-bound gameplay artifact.",
                "model_calls": team.call_count,
            })
            store.update(record)
            deterministic = await asyncio.to_thread(
                toolpack.evidence_adapter.verify,
                artifact,
                root,
                evidence_dir,
                brief.acceptance_criteria,
            )
            store.put_json(run_id, "sprites/final/deterministic_evidence.json", deterministic.model_dump(mode="json"))
            for evidence_file in sorted(evidence_dir.iterdir()):
                if evidence_file.is_file() and evidence_file.suffix in {".json", ".png"}:
                    media_type = "image/png" if evidence_file.suffix == ".png" else "application/json"
                    store.put_file(run_id, f"sprites/final/evidence/{evidence_file.name}", evidence_file, media_type)
        if not deterministic.passed:
            raise RuntimeError(f"final sprite-bound Godot runtime failed: {'; '.join(deterministic.issues)}")
        sprite_observation = (
            f"Independent Sprite Atlas Gate approved {len(sprite_plan.slots)} bound slots; "
            "the final Godot probe loaded the atlas and mapped every declared hero and enemy ID."
        )
        deterministic = deterministic.model_copy(update={
            "criterion_evidence": {
                criterion: [*deterministic.criterion_evidence.get(criterion, []), sprite_observation]
                for criterion in brief.acceptance_criteria
            }
        })
        store.put_json(run_id, "sprites/final/deterministic_evidence.json", deterministic.model_dump(mode="json"))

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
            verification_payload = {
                "approved_brief": brief.model_dump(mode="json"),
                "quest": quest.model_dump(mode="json"),
                "gameplay_plan": decision.gameplay.model_dump(mode="json"),
                "visual_concept": artifact.concept.model_dump(mode="json"),
                "compiled_artifact": {
                    "plan_sha256": artifact.plan_sha256,
                    "bundle_sha256": artifact.bundle_sha256,
                    "files": sorted(artifact.files),
                    "asset_sha256": artifact.asset.sha256,
                    "sprite_atlas_sha256": artifact.sprite_atlas.sha256 if artifact.sprite_atlas else None,
                    "sprite_atlas_plan": sprite_plan.model_dump(mode="json"),
                    "sprite_atlas_gate": sprite_gate.model_dump(mode="json"),
                },
                "deterministic_evidence": deterministic.model_dump(mode="json"),
            }
            verification = await team.verify_godot(verification_payload) if deterministic.passed else _blocked(
                quest.acceptance_criteria, deterministic.issues,
            )
            if deterministic.passed and len(verification.findings) != len(quest.acceptance_criteria):
                verification = await team.verify_godot({
                    **verification_payload,
                    "format_repair": {
                        "reason": "The prior response did not return exactly one finding per active criterion.",
                        "required_criteria_in_order": quest.acceptance_criteria,
                        "required_finding_count": len(quest.acceptance_criteria),
                        "instruction": "Return a fresh complete verification object; do not omit or combine findings.",
                    },
                })
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

        capability_trace = build_agent_capability_trace(
            profile_id="godot.trinity-top-down",
            plan_sha256=artifact.plan_sha256,
            artifact_bundle_sha256=artifact.bundle_sha256,
            evidence_sha256=canonical_sha256(deterministic),
            composition=compose_godot_gameplay_capabilities(
                artifact.gameplay, artifact.sprite_plan
            ),
            profile=GODOT_GAMEPLAY_SPRITE_PROFILE,
            binary_sha256_by_path={
                artifact.asset.path: artifact.asset.sha256,
                artifact.sprite_atlas.path: artifact.sprite_atlas.sha256,
            },
            model_calls_by_agent=getattr(team, "call_count_by_agent", {}),
        )
        capability_trace_uri = store.put_json(
            run_id,
            "final/agent-capability-trace.json",
            capability_trace.model_dump(mode="json"),
        )

        with tempfile.TemporaryDirectory(prefix=f"khalinos-gameplay-final-{run_id}-") as temporary:
            archive = Path(temporary) / "source.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
                for raw_path, content in sorted(artifact.files.items()):
                    output.writestr(raw_path, content.encode("utf-8"))
                output.writestr(artifact.asset.path, artifact.asset.bytes())
                if artifact.sprite_atlas is not None:
                    output.writestr(artifact.sprite_atlas.path, artifact.sprite_atlas.bytes())
            archive_uri = store.put_file(run_id, "final/source.zip", archive, "application/zip")
        store.put_json(run_id, "final/artifact_manifest.json", {
            "artifact_sha256": canonical_sha256(artifact),
            "plan_sha256": artifact.plan_sha256,
            "bundle_sha256": artifact.bundle_sha256,
            "asset_sha256": artifact.asset.sha256,
            "sprite_atlas_sha256": artifact.sprite_atlas.sha256 if artifact.sprite_atlas else None,
            "sprite_atlas_gate_sha256": canonical_sha256(sprite_gate),
            "sprite_segmentation_contract_sha256": artifact.sprite_segmentation_contract_sha256,
            "toolpack_binding": binding.model_dump(mode="json"),
            "agent_capability_trace_sha256": capability_trace.sha256(),
            "agent_capability_trace": capability_trace_uri,
            "files": sorted([*artifact.files, artifact.asset.path, *([artifact.sprite_atlas.path] if artifact.sprite_atlas else [])]),
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
