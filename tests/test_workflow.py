from __future__ import annotations

import json
import struct
import threading
import zlib
from pathlib import Path

from khalinos.browser_toolpack import BROWSER_PRODUCT_MANIFEST, BROWSER_PRODUCT_TOOLPACK
from khalinos.models import (
    AgentVerification,
    ArtifactBundle,
    ArtifactFile,
    CriterionFinding,
    DeterministicEvidence,
    QuestPlan,
    QuestSpec,
    ProjectRecord,
    RunRecord,
    RunStatus,
    UserBrief,
    VisualAssessment,
    VisualAssetGate,
    VisualConcept,
    VisualConceptPlan,
    VisualSelection,
    canonical_sha256,
)
from khalinos.storage import LocalRunStore
from khalinos.toolpacks import RegisteredToolPack, ToolPackBinding, ToolPackRegistry
from khalinos.projects import LocalProjectStore
from khalinos.workflow import _bind_plan_authority, _enforce_verification_contract, _validate_plan_authority, execute_run
from khalinos.visual_assets import trusted_png_asset


def valid_png(width: int = 256, height: int = 256) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    rows = b"".join(
        b"\x00" + bytes(value for x in range(width) for value in (x, y, (x * 31 + y * 17) % 256, 255))
        for y in range(height)
    )
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def runtime_criterion_evidence(args: tuple[object, ...]) -> dict[str, list[str]]:
    criteria = args[3] if len(args) > 3 else []
    return {str(criterion): ["typed runtime assertion observed"] for criterion in criteria}


class StubEvidenceAdapter:
    adapter_id = BROWSER_PRODUCT_MANIFEST.evidence.adapter_id

    def __init__(self, callback) -> None:
        self.callback = callback

    def verify(self, artifact, root, evidence_dir, acceptance_criteria):
        return self.callback(artifact, root, evidence_dir, acceptance_criteria)


def toolpack_with_evidence(callback) -> RegisteredToolPack:
    return RegisteredToolPack(
        manifest=BROWSER_PRODUCT_MANIFEST,
        execution_adapter=BROWSER_PRODUCT_TOOLPACK.execution_adapter,
        evidence_adapter=StubEvidenceAdapter(callback),
    )


def bundle(summary: str = "Runnable complete revision") -> ArtifactBundle:
    values = {
        "index.html": "<!doctype html><html><button aria-label='Go'>Go</button><p>Ready</p></html>",
        "styles.css": "button{color:white}@media(max-width:600px){button{width:100%}}",
        "app.js": "document.querySelector('button').addEventListener('click',()=>{});",
        "journey.json": json.dumps({"journeys": [{"name": "primary", "steps": [{"click": "button"}, {"assert_text": "Ready"}]}]}),
        "README.md": "# Generated product\n\nRun with a static file server.",
    }
    return ArtifactBundle(revision_summary=summary, files=[ArtifactFile(path=key, content=value) for key, value in values.items()])


class FakeTeam:
    def __init__(self) -> None:
        self.call_count = 0
        self.repairs = 0

    async def plan(self, payload: dict) -> QuestPlan:
        self.call_count += 1
        assert "approved_brief" in payload
        return QuestPlan(
            product_summary="A bounded interactive browser product generated from the approved brief.",
            architecture_decision="Use a self-contained accessible HTML, CSS, and JavaScript application.",
            quests=[
                QuestSpec(quest_id="Q1", objective="Create a runnable shell and primary interaction.", acceptance_criteria=["The primary action works."], evidence_required=["Browser journey."]),
                QuestSpec(quest_id="Q2", objective="Complete responsive behavior and final verification.", acceptance_criteria=["The interface is responsive."], evidence_required=["Runtime screenshot."], depends_on=["Q1"]),
            ],
        )

    async def make(self, payload: dict) -> ArtifactBundle:
        self.call_count += 1
        return bundle(f"Completed {payload['quest']['quest_id']}")

    async def verify(self, payload: dict) -> AgentVerification:
        self.call_count += 1
        criterion = payload["quest"]["acceptance_criteria"][0]
        return AgentVerification(findings=[CriterionFinding(criterion=criterion, passed=True, evidence="Runtime journey passed.")], verdict="PASS")

    async def repair(self, payload: dict) -> ArtifactBundle:
        self.call_count += 1
        self.repairs += 1
        return bundle("Technical repair completed")

    async def plan_visuals(self, payload: dict) -> VisualConceptPlan:
        self.call_count += 1
        return VisualConceptPlan(
            shared_contract="A polished, accessible visual foundation for the approved browser product.",
            candidates=[
                VisualConcept(
                    candidate_id=f"V{index}",
                    name=name,
                    design_thesis=f"Create a distinct {name} composition that clearly expresses the approved product purpose.",
                    composition="Use a clear primary workspace with a strong focal action and balanced supporting information.",
                    typography="Use a deliberate type hierarchy with readable controls.",
                    palette=["charcoal", "ivory", accent],
                    interaction_emphasis="Make the primary action and current state immediately legible.",
                    anti_goals=["generic template cards", "decorative clutter"],
                )
                for index, (name, accent) in enumerate([
                    ("Editorial", "brass"),
                    ("Instrument", "cobalt"),
                    ("Tactile", "terracotta"),
                ], start=1)
            ],
        )

    async def make_visual(self, payload: dict) -> ArtifactBundle:
        self.call_count += 1
        return bundle(f"Visual foundation {payload['visual_concept']['candidate_id']}")

    async def make_visual_asset(self, brief, concept):
        self.call_count += 1
        return trusted_png_asset(valid_png())

    async def verify_visual_asset(self, candidate_id, asset, concept):
        self.call_count += 1
        return VisualAssetGate(
            candidate_id=candidate_id,
            approved=True,
            contains_text_or_glyphs=False,
            contains_interface_elements=False,
            contains_logo_or_watermark=False,
            rationale="The raw PNG contains only a bounded environmental layer without forbidden content.",
        )

    async def select_visual(self, payload: dict, screenshots: list[tuple[str, bytes]]) -> VisualSelection:
        self.call_count += 1
        ids = [candidate_id for candidate_id, _ in screenshots]
        assessments = [
            VisualAssessment(
                candidate_id=candidate_id,
                contract_alignment=9 if candidate_id == ids[0] else 8,
                visual_hierarchy=9,
                distinctiveness=9 if candidate_id == ids[0] else 8,
                interaction_clarity=9,
                craft_and_cohesion=9,
                strengths=["Clear visual foundation."],
            )
            for candidate_id in ids
        ]
        return VisualSelection(
            assessments=assessments,
            selected_candidate_id=ids[0],
            rationale="The selected candidate has the strongest verified hierarchy and contract alignment.",
        )


def setup_run(tmp_path: Path) -> tuple[LocalRunStore, str]:
    store = LocalRunStore(tmp_path)
    brief = UserBrief(
        project_name="Demo",
        goal="Create a small interactive decision product with one complete browser workflow.",
        acceptance_criteria=["The primary action works.", "The interface is responsive."],
        toolpack_binding=BROWSER_PRODUCT_TOOLPACK.binding(),
        authorized_output_files=list(BROWSER_PRODUCT_MANIFEST.output.authorized_paths),
    )
    run_id = "a" * 32
    store.create(RunRecord(
        run_id=run_id,
        status=RunStatus.QUEUED,
        brief_sha256=canonical_sha256(brief),
        toolpack_binding=BROWSER_PRODUCT_TOOLPACK.binding(),
        message="Queued.",
    ), brief)
    return store, run_id


def test_source_claim_cannot_replace_direct_runtime_criterion_evidence() -> None:
    criterion = "The random extra reveal is observable at runtime."
    claimed = AgentVerification(
        findings=[CriterionFinding(
            criterion=criterion,
            passed=True,
            evidence="The source contains a random reveal function.",
        )],
        verdict="PASS",
    )

    enforced = _enforce_verification_contract([criterion], {}, claimed)

    assert enforced.verdict == "REPAIR"
    assert not enforced.findings[0].passed
    assert "lack typed assertion evidence" in enforced.findings[0].evidence


def test_host_binds_ordered_verifier_findings_to_immutable_criteria() -> None:
    criteria = ["Increase changes the count.", "Reset restores zero."]
    paraphrased = AgentVerification(
        findings=[
            CriterionFinding(criterion="Increment works.", passed=True, evidence="Observed Count: 1."),
            CriterionFinding(criterion="Reset works.", passed=True, evidence="Observed Count: 0."),
        ],
        verdict="PASS",
    )
    evidence = {criterion: ["typed runtime assertion observed"] for criterion in criteria}

    enforced = _enforce_verification_contract(criteria, evidence, paraphrased)

    assert enforced.verdict == "PASS"
    assert [item.criterion for item in enforced.findings] == criteria


def test_project_owner_cannot_promote_evidence_mechanics_to_product_criteria() -> None:
    brief = UserBrief(
        project_name="Counter",
        goal="Repair a compact counter so increment and reset behavior work in the browser.",
        acceptance_criteria=["Increase changes the count.", "Reset restores zero."],
        authorized_output_files=list(BROWSER_PRODUCT_MANIFEST.output.authorized_paths),
    )
    widened = QuestPlan(
        product_summary="A bounded browser counter with a verified increment and reset interaction.",
        architecture_decision="Use the fixed offline HTML, CSS, and JavaScript product surface.",
        quests=[
            QuestSpec(
                quest_id="Q1",
                objective="Repair the approved counter increment behavior without widening scope.",
                acceptance_criteria=["Increase changes the count."],
                evidence_required=["A criterion-bound browser journey."],
            ),
            QuestSpec(
                quest_id="Q2",
                objective="Verify reset behavior and the complete approved counter outcome.",
                acceptance_criteria=["Reset restores zero.", "Expose a downloadable verification log."],
                evidence_required=["A criterion-bound browser journey."],
                depends_on=["Q1"],
            ),
        ],
    )

    try:
        _validate_plan_authority(brief, widened)
    except PermissionError as exc:
        assert "invented criteria" in str(exc)
        assert "downloadable verification log" in str(exc)
    else:
        raise AssertionError("widened Project Owner criteria must be rejected")


def test_project_owner_cannot_repeat_an_approved_criterion_across_quests() -> None:
    brief = UserBrief(
        project_name="Counter",
        goal="Repair a compact counter so increment and reset behavior work in the browser.",
        acceptance_criteria=["Increase changes the count.", "Reset restores zero."],
        authorized_output_files=list(BROWSER_PRODUCT_MANIFEST.output.authorized_paths),
    )
    repeated = QuestPlan(
        product_summary="A bounded browser counter with verified increment and reset behavior.",
        architecture_decision="Use the fixed offline browser artifact and runtime verification surface.",
        quests=[
            QuestSpec(
                quest_id="Q1",
                objective="Repair and verify the approved counter increment behavior without widening scope.",
                acceptance_criteria=["Increase changes the count."],
                evidence_required=["A criterion-bound browser journey."],
            ),
            QuestSpec(
                quest_id="Q2",
                objective="Verify the reset behavior and complete the approved counter outcome.",
                acceptance_criteria=["Increase changes the count.", "Reset restores zero."],
                evidence_required=["A criterion-bound browser journey."],
                depends_on=["Q1"],
            ),
        ],
    )

    try:
        _validate_plan_authority(brief, repeated)
    except PermissionError as exc:
        assert "exactly once" in str(exc)
    else:
        raise AssertionError("repeated approved criteria must be rejected")


def test_trusted_host_binds_verbatim_criteria_over_model_paraphrases() -> None:
    criteria = [
        "The opening encounter is beatable at level one.",
        "Every hero basic attack is visibly distinct.",
        "Active skills use cooldowns and separate effects.",
    ]
    brief = UserBrief(
        project_name="Trinity Trial",
        goal="Build and prove a bounded Godot combat slice.",
        acceptance_criteria=criteria,
        authorized_output_files=list(BROWSER_PRODUCT_MANIFEST.output.authorized_paths),
    )
    proposed = QuestPlan(
        product_summary="A bounded combat slice with runtime evidence.",
        architecture_decision="Use the approved trusted compiler and evidence adapter.",
        quests=[
            QuestSpec(
                quest_id="Q1",
                objective="Build the opening combat loop.",
                acceptance_criteria=["Level one can win the opening fight."],
                evidence_required=["Runtime combat probe."],
            ),
            QuestSpec(
                quest_id="Q2",
                objective="Prove readable role feedback.",
                acceptance_criteria=["Show attacks, cooldowns, and effects."],
                evidence_required=["Rendered frame and runtime probe."],
                depends_on=["Q1"],
            ),
        ],
    )

    bound = _bind_plan_authority(brief, proposed)

    assert [item for quest in bound.quests for item in quest.acceptance_criteria] == criteria
    assert bound.quests[0].acceptance_criteria == criteria[:2]
    assert bound.quests[1].acceptance_criteria == criteria[2:]


def test_trusted_host_rejects_more_quests_than_approved_criteria() -> None:
    criteria = ["Opening passes.", "Feedback passes."]
    brief = UserBrief(
        project_name="Trinity Trial",
        goal="Build and prove a bounded Godot combat slice.",
        acceptance_criteria=criteria,
        authorized_output_files=list(BROWSER_PRODUCT_MANIFEST.output.authorized_paths),
    )
    proposed = QuestPlan(
        product_summary="A bounded combat slice with runtime evidence.",
        architecture_decision="Use the approved trusted compiler and evidence adapter.",
        quests=[
            QuestSpec(
                quest_id=f"Q{index}",
                objective=f"Proposed work unit {index}.",
                acceptance_criteria=[f"Paraphrased criterion {index}."],
                evidence_required=["Runtime evidence."],
                depends_on=[] if index == 1 else [f"Q{index - 1}"],
            )
            for index in range(1, 4)
        ],
    )

    try:
        _bind_plan_authority(brief, proposed)
    except PermissionError as exc:
        assert "more Quests" in str(exc)
    else:
        raise AssertionError("the host must not create empty-authority Quests")


async def test_full_run_passes_without_human_or_coding_assistant(monkeypatch, tmp_path: Path) -> None:
    def evidence(*args, **kwargs):
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(passed=True, checks={"runtime": True}, issues=[], screenshot_names=["journey-01.png"], criterion_evidence=runtime_criterion_evidence(args))
    active_toolpack = toolpack_with_evidence(evidence)
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team, registry=ToolPackRegistry([active_toolpack]))
    assert result.status == RunStatus.PASSED
    assert len(result.completed_receipt_ids) == 3
    assert result.completed_receipt_ids[0].startswith("VS-")
    assert team.repairs == 0
    expected_binding = BROWSER_PRODUCT_TOOLPACK.binding().model_dump(mode="json")
    plan = json.loads((tmp_path / "runs" / run_id / "quest_plan.json").read_text(encoding="utf-8"))
    receipt = json.loads((tmp_path / "runs" / run_id / "quests" / "Q1" / "receipt.json").read_text(encoding="utf-8"))
    final_manifest = json.loads((tmp_path / "runs" / run_id / "final" / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert plan["toolpack_binding"] == expected_binding
    assert receipt["toolpack_binding"] == expected_binding
    assert final_manifest["toolpack_binding"] == expected_binding
    assert final_manifest["assets"][0]["path"] == "assets/visual-foundation.png"
    visual_receipt = json.loads((tmp_path / "runs" / run_id / "visuals" / "selection_receipt.json").read_text(encoding="utf-8"))
    assert visual_receipt["asset_sha256_by_candidate"][visual_receipt["selected_candidate_id"]]


async def test_run_stops_before_planning_when_toolpack_binding_is_tampered(tmp_path: Path) -> None:
    store, run_id = setup_run(tmp_path)
    record = store.read_record(run_id)
    approved = BROWSER_PRODUCT_TOOLPACK.binding()
    tampered = ToolPackBinding(
        toolpack_id=approved.toolpack_id,
        version=approved.version,
        manifest_sha256="0" * 64,
    )
    store.update(record.model_copy(update={"toolpack_binding": tampered}))
    team = FakeTeam()

    result = await execute_run(
        run_id,
        store=store,
        team=team,
        registry=ToolPackRegistry([BROWSER_PRODUCT_TOOLPACK]),
    )

    assert result.status == RunStatus.FAILED
    assert "same ToolPack binding" in result.message
    assert team.call_count == 0


async def test_passed_run_registers_verified_project_checkpoint(monkeypatch, tmp_path: Path) -> None:
    def evidence(*args, **kwargs):
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(passed=True, checks={"runtime": True}, issues=[], screenshot_names=["journey-01.png"], criterion_evidence=runtime_criterion_evidence(args))

    active_toolpack = toolpack_with_evidence(evidence)
    store, run_id = setup_run(tmp_path)
    project_store = LocalProjectStore(tmp_path)
    project_store.prepare(ProjectRecord(
        project_id="b" * 32,
        owner_id="owner-a",
        display_name="Demo",
        latest_run_id=run_id,
        latest_status=RunStatus.QUEUED,
    ))
    record = store.read_record(run_id).model_copy(update={"owner_id": "owner-a", "project_id": "b" * 32})
    store.update(record)
    result = await execute_run(run_id, store=store, team=FakeTeam(), registry=ToolPackRegistry([active_toolpack]), project_store=project_store)
    registered = project_store.read_owned("b" * 32, "owner-a")
    assert result.status == RunStatus.PASSED
    assert registered.latest_status == RunStatus.PASSED
    assert registered.latest_run_id == run_id
    assert registered.latest_checkpoint_sha256 is not None
    assert registered.source_snapshot is not None


async def test_existing_project_enters_through_technical_repair_without_visual_regeneration(monkeypatch, tmp_path: Path) -> None:
    def evidence(*args, **kwargs):
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(passed=True, checks={"runtime": True}, issues=[], screenshot_names=["journey-01.png"], criterion_evidence=runtime_criterion_evidence(args))

    active_toolpack = toolpack_with_evidence(evidence)
    store, run_id = setup_run(tmp_path)
    starting = bundle("Existing verified project")
    snapshot = store.put_bundle_archive("source" * 5 + "ab", starting)
    record = store.read_record(run_id).model_copy(update={
        "work_mode": "existing_project_repair",
        "source_snapshot": snapshot,
    })
    store.update(record)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team, registry=ToolPackRegistry([active_toolpack]))
    assert result.status == RunStatus.PASSED
    assert team.repairs == 2
    assert result.completed_receipt_ids[0].startswith("SR-")
    assert not (tmp_path / "runs" / run_id / "visuals").exists()


async def test_deterministic_browser_verification_runs_off_event_loop_thread(monkeypatch, tmp_path: Path) -> None:
    event_loop_thread = threading.get_ident()
    verifier_threads: list[int] = []

    def evidence(*args, **kwargs):
        verifier_threads.append(threading.get_ident())
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(
            passed=True,
            checks={"runtime": True},
            issues=[],
            screenshot_names=["journey-01.png"],
            criterion_evidence=runtime_criterion_evidence(args),
        )

    active_toolpack = toolpack_with_evidence(evidence)
    store, run_id = setup_run(tmp_path)
    result = await execute_run(run_id, store=store, team=FakeTeam(), registry=ToolPackRegistry([active_toolpack]))

    assert result.status == RunStatus.PASSED
    assert verifier_threads
    assert all(thread_id != event_loop_thread for thread_id in verifier_threads)


async def test_each_later_quest_rechecks_all_previously_verified_criteria(tmp_path: Path) -> None:
    runtime_contracts: list[list[str]] = []

    def evidence(*args, **kwargs):
        criteria = list(args[3])
        if criteria:
            runtime_contracts.append(criteria)
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(
            passed=True,
            checks={"runtime": True},
            issues=[],
            screenshot_names=["journey-01.png"],
            criterion_evidence=runtime_criterion_evidence(args),
        )

    store, run_id = setup_run(tmp_path)
    result = await execute_run(
        run_id,
        store=store,
        team=FakeTeam(),
        registry=ToolPackRegistry([toolpack_with_evidence(evidence)]),
    )
    assert result.status == RunStatus.PASSED
    assert runtime_contracts == [
        ["The primary action works."],
        ["The primary action works.", "The interface is responsive."],
    ]


async def test_visual_competition_continues_with_two_renderable_candidates(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    def evidence(*args, **kwargs):
        calls["count"] += 1
        visual_candidate_two = calls["count"] == 2
        evidence_dir = args[2]
        if not visual_candidate_two:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(
            passed=not visual_candidate_two,
            checks={"runtime": not visual_candidate_two},
            issues=["candidate did not render"] if visual_candidate_two else [],
            screenshot_names=[] if visual_candidate_two else ["journey-01.png"],
            criterion_evidence=runtime_criterion_evidence(args),
        )

    active_toolpack = toolpack_with_evidence(evidence)
    store, run_id = setup_run(tmp_path)
    result = await execute_run(run_id, store=store, team=FakeTeam(), registry=ToolPackRegistry([active_toolpack]))

    assert result.status == RunStatus.PASSED
    receipt = json.loads((tmp_path / "runs" / run_id / "visuals" / "selection_receipt.json").read_text(encoding="utf-8"))
    assert receipt["eligible_candidate_ids"] == ["V1", "V3"]
    assert list(receipt["selection"]["assessments"][index]["candidate_id"] for index in range(2)) == ["V1", "V3"]


async def test_visual_asset_gate_rejects_forbidden_raw_image_before_browser_maker(tmp_path: Path) -> None:
    def evidence(*args, **kwargs):
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(
            passed=True,
            checks={"runtime": True},
            issues=[],
            screenshot_names=["journey-01.png"],
            criterion_evidence=runtime_criterion_evidence(args),
        )

    team = FakeTeam()
    original_gate = team.verify_visual_asset

    async def gate(candidate_id, asset, concept):
        if candidate_id == "V2":
            team.call_count += 1
            return VisualAssetGate(
                candidate_id="V2",
                approved=False,
                contains_text_or_glyphs=True,
                contains_interface_elements=False,
                contains_logo_or_watermark=False,
                issues=["Readable title detected in the raw PNG."],
                rationale="The raw PNG contains a readable title and cannot be used as a trusted background.",
            )
        return await original_gate(candidate_id, asset, concept)

    team.verify_visual_asset = gate
    store, run_id = setup_run(tmp_path)
    result = await execute_run(
        run_id,
        store=store,
        team=team,
        registry=ToolPackRegistry([toolpack_with_evidence(evidence)]),
    )
    assert result.status == RunStatus.PASSED
    run_root = tmp_path / "runs" / run_id
    rejected = json.loads((run_root / "visuals" / "V2" / "asset_gate.json").read_text(encoding="utf-8"))
    assert not rejected["approved"]
    assert not (run_root / "visuals" / "V2" / "product").exists()
    selection = json.loads((run_root / "visuals" / "selection_receipt.json").read_text(encoding="utf-8"))
    assert selection["eligible_candidate_ids"] == ["V1", "V3"]


async def test_deterministic_failure_routes_to_bounded_technical_repair(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    def evidence(*args, **kwargs):
        calls["count"] += 1
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        passed = calls["count"] != 4
        return DeterministicEvidence(passed=passed, checks={"runtime": passed}, issues=[] if passed else ["runtime failed"], criterion_evidence=runtime_criterion_evidence(args) if passed else {})
    active_toolpack = toolpack_with_evidence(evidence)
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team, registry=ToolPackRegistry([active_toolpack]))
    assert result.status == RunStatus.PASSED
    assert team.repairs == 1


async def test_third_failure_stops_instead_of_looping(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    def evidence(*args, **kwargs):
        calls["count"] += 1
        visual = calls["count"] <= 3
        evidence_dir = args[2]
        if visual:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(
            passed=visual,
            checks={"runtime": visual},
            issues=[] if visual else ["same structural failure"],
            screenshot_names=["journey-01.png"] if visual else [],
            criterion_evidence=runtime_criterion_evidence(args) if visual else {},
        )
    active_toolpack = toolpack_with_evidence(evidence)
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team, registry=ToolPackRegistry([active_toolpack]))
    assert result.status == RunStatus.BLOCKED
    assert team.repairs == 2
