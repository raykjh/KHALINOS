from __future__ import annotations

import json
import threading
from pathlib import Path

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
    VisualConcept,
    VisualConceptPlan,
    VisualSelection,
    canonical_sha256,
)
from khalinos.storage import LocalRunStore
from khalinos.projects import LocalProjectStore
from khalinos.workflow import _enforce_verification_contract, _validate_plan_authority, execute_run


def runtime_criterion_evidence(args: tuple[object, ...]) -> dict[str, list[str]]:
    criteria = args[3] if len(args) > 3 else []
    return {str(criterion): ["typed runtime assertion observed"] for criterion in criteria}


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
    )
    run_id = "a" * 32
    store.create(RunRecord(run_id=run_id, status=RunStatus.QUEUED, brief_sha256=canonical_sha256(brief), message="Queued."), brief)
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


async def test_full_run_passes_without_human_or_coding_assistant(monkeypatch, tmp_path: Path) -> None:
    def evidence(*args, **kwargs):
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(passed=True, checks={"runtime": True}, issues=[], screenshot_names=["journey-01.png"], criterion_evidence=runtime_criterion_evidence(args))
    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team)
    assert result.status == RunStatus.PASSED
    assert len(result.completed_receipt_ids) == 3
    assert result.completed_receipt_ids[0].startswith("VS-")
    assert team.repairs == 0


async def test_passed_run_registers_verified_project_checkpoint(monkeypatch, tmp_path: Path) -> None:
    def evidence(*args, **kwargs):
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        return DeterministicEvidence(passed=True, checks={"runtime": True}, issues=[], screenshot_names=["journey-01.png"], criterion_evidence=runtime_criterion_evidence(args))

    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
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
    result = await execute_run(run_id, store=store, team=FakeTeam(), project_store=project_store)
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

    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    starting = bundle("Existing verified project")
    snapshot = store.put_bundle_archive("source" * 5 + "ab", starting)
    record = store.read_record(run_id).model_copy(update={
        "work_mode": "existing_project_repair",
        "source_snapshot": snapshot,
    })
    store.update(record)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team)
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

    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    result = await execute_run(run_id, store=store, team=FakeTeam())

    assert result.status == RunStatus.PASSED
    assert verifier_threads
    assert all(thread_id != event_loop_thread for thread_id in verifier_threads)


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

    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    result = await execute_run(run_id, store=store, team=FakeTeam())

    assert result.status == RunStatus.PASSED
    receipt = json.loads((tmp_path / "runs" / run_id / "visuals" / "selection_receipt.json").read_text(encoding="utf-8"))
    assert receipt["eligible_candidate_ids"] == ["V1", "V3"]
    assert list(receipt["selection"]["assessments"][index]["candidate_id"] for index in range(2)) == ["V1", "V3"]


async def test_deterministic_failure_routes_to_bounded_technical_repair(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    def evidence(*args, **kwargs):
        calls["count"] += 1
        evidence_dir = args[2]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "journey-01.png").write_bytes(b"png")
        passed = calls["count"] != 4
        return DeterministicEvidence(passed=passed, checks={"runtime": passed}, issues=[] if passed else ["runtime failed"], criterion_evidence=runtime_criterion_evidence(args) if passed else {})
    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team)
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
    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team)
    assert result.status == RunStatus.BLOCKED
    assert team.repairs == 2
