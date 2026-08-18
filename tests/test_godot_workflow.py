from __future__ import annotations

import json
from pathlib import Path

from khalinos.godot_toolpack import GODOT_TOPOLOGY_MANIFEST, GODOT_TOPOLOGY_TOOLPACK
from khalinos.godot_topology import GodotProjectPlan, GodotRegion, GodotTopologyPlan
from khalinos.godot_workflow import execute_godot_run
from khalinos.models import (
    AgentVerification,
    CriterionFinding,
    DeterministicEvidence,
    QuestPlan,
    QuestSpec,
    RunRecord,
    RunStatus,
    UserBrief,
    canonical_sha256,
)
from khalinos.run_router import execute_authorized_run
from khalinos.storage import LocalRunStore
from khalinos.toolpacks import RegisteredToolPack, ToolPackRegistry


CRITERIA = [
    "The project opens on an arrival screen.",
    "Every declared screen loads successfully in Godot headless verification.",
]


class StubGodotEvidenceAdapter:
    adapter_id = GODOT_TOPOLOGY_MANIFEST.evidence.adapter_id

    def verify(self, artifact, root, evidence_dir, acceptance_criteria):
        assert (root / "project.godot").is_file()
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "godot-topology-probe.json").write_text(
            json.dumps({"visited": [item.region_id for item in artifact.plan.regions]}),
            encoding="utf-8",
        )
        return DeterministicEvidence(
            passed=True,
            checks={"headless_process": True, "all_regions_loaded": True},
            issues=[],
            criterion_evidence={
                criterion: ["Digest-bound headless topology probe passed."]
                for criterion in acceptance_criteria
            },
        )


def stub_toolpack() -> RegisteredToolPack:
    return RegisteredToolPack(
        manifest=GODOT_TOPOLOGY_MANIFEST,
        execution_adapter=GODOT_TOPOLOGY_TOOLPACK.execution_adapter,
        evidence_adapter=StubGodotEvidenceAdapter(),
    )


class FakeGodotTeam:
    def __init__(self, *, project_name: str = "Route Observatory") -> None:
        self.call_count = 0
        self.project_name = project_name

    async def plan_godot(self, payload: dict) -> GodotProjectPlan:
        self.call_count += 1
        assert payload["approved_brief"]["toolpack_binding"]
        return GodotProjectPlan(
            quest_plan=QuestPlan(
                product_summary="A bounded offline Godot screen topology generated from the approved brief.",
                architecture_decision="Use only the trusted topology compiler and its fixed headless evidence probe.",
                quests=[
                    QuestSpec(
                        quest_id="Q1",
                        objective="Materialize the approved arrival surface through the trusted Godot compiler.",
                        acceptance_criteria=[CRITERIA[0]],
                        evidence_required=["Digest-bound Godot headless probe receipt."],
                    ),
                    QuestSpec(
                        quest_id="Q2",
                        objective="Verify every connected region in the approved topology without widening scope.",
                        acceptance_criteria=[CRITERIA[1]],
                        evidence_required=["Digest-bound Godot headless probe receipt."],
                        depends_on=["Q1"],
                    ),
                ],
            ),
            topology=GodotTopologyPlan(
                project_name=self.project_name,
                initial_region="arrival",
                regions=(
                    GodotRegion(region_id="arrival", label="Arrival", transitions=("workspace",)),
                    GodotRegion(region_id="workspace", label="Workspace", transitions=("result",)),
                    GodotRegion(region_id="result", label="Verified Result"),
                ),
            ),
        )

    async def verify_godot(self, payload: dict) -> AgentVerification:
        self.call_count += 1
        criterion = payload["quest"]["acceptance_criteria"][0]
        return AgentVerification(
            findings=[CriterionFinding(
                criterion=criterion,
                passed=True,
                evidence="Independent review matched the criterion to the headless probe receipt.",
            )],
            verdict="PASS",
        )


def setup_run(tmp_path: Path) -> tuple[LocalRunStore, str, ToolPackRegistry]:
    toolpack = stub_toolpack()
    binding = toolpack.binding()
    brief = UserBrief(
        project_name="Route Observatory",
        goal="Create a bounded offline Godot topology with an arrival, workspace, and verified result screen.",
        acceptance_criteria=CRITERIA,
        max_quests=2,
        toolpack_binding=binding,
        authorized_output_files=list(toolpack.manifest.output.authorized_paths),
    )
    run_id = "d" * 32
    store = LocalRunStore(tmp_path)
    store.create(
        RunRecord(
            run_id=run_id,
            status=RunStatus.QUEUED,
            brief_sha256=canonical_sha256(brief),
            toolpack_binding=binding,
            message="Queued.",
            work_mode="new_product_build",
        ),
        brief,
    )
    return store, run_id, ToolPackRegistry([toolpack])


async def test_godot_vertical_path_binds_plan_artifact_evidence_and_receipts(tmp_path: Path) -> None:
    store, run_id, registry = setup_run(tmp_path)
    result = await execute_godot_run(
        run_id,
        store=store,
        team=FakeGodotTeam(),
        registry=registry,
    )

    assert result.status == RunStatus.PASSED
    assert len(result.completed_receipt_ids) == 2
    run_root = tmp_path / "runs" / run_id
    plan = json.loads((run_root / "quest_plan.json").read_text(encoding="utf-8"))
    first = json.loads((run_root / "quests" / "Q1" / "receipt.json").read_text(encoding="utf-8"))
    second = json.loads((run_root / "quests" / "Q2" / "receipt.json").read_text(encoding="utf-8"))
    final = json.loads((run_root / "final" / "artifact_manifest.json").read_text(encoding="utf-8"))
    expected_binding = registry.binding_for("godot.topology").model_dump(mode="json")
    assert plan["toolpack_binding"] == expected_binding
    assert first["toolpack_binding"] == expected_binding
    assert second["parent_receipt_id"] == first["receipt_id"]
    assert final["toolpack_binding"] == expected_binding
    assert final["receipt_ids"] == result.completed_receipt_ids
    assert (run_root / "final" / "source.zip").is_file()


async def test_godot_router_dispatches_by_exact_approved_binding(tmp_path: Path) -> None:
    store, run_id, registry = setup_run(tmp_path)
    result = await execute_authorized_run(
        run_id,
        store=store,
        team=FakeGodotTeam(),
        registry=registry,
    )
    assert result.status == RunStatus.PASSED
    assert "Godot topology" in result.message


async def test_godot_owner_cannot_change_the_approved_project_name(tmp_path: Path) -> None:
    store, run_id, registry = setup_run(tmp_path)
    result = await execute_godot_run(
        run_id,
        store=store,
        team=FakeGodotTeam(project_name="Unauthorized Product"),
        registry=registry,
    )
    assert result.status == RunStatus.FAILED
    assert "changed the approved project name" in result.message
    assert not (tmp_path / "runs" / run_id / "final" / "source.zip").exists()
