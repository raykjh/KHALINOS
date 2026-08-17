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
    RunRecord,
    RunStatus,
    UserBrief,
    canonical_sha256,
)
from khalinos.storage import LocalRunStore
from khalinos.workflow import execute_run


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


async def test_full_run_passes_without_human_or_coding_assistant(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("khalinos.workflow.verify_bundle", lambda *args, **kwargs: DeterministicEvidence(passed=True, checks={"runtime": True}, issues=[], screenshot_names=["journey-01.png"]))
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team)
    assert result.status == RunStatus.PASSED
    assert len(result.completed_receipt_ids) == 2
    assert team.repairs == 0


async def test_deterministic_browser_verification_runs_off_event_loop_thread(monkeypatch, tmp_path: Path) -> None:
    event_loop_thread = threading.get_ident()
    verifier_threads: list[int] = []

    def evidence(*args, **kwargs):
        verifier_threads.append(threading.get_ident())
        return DeterministicEvidence(
            passed=True,
            checks={"runtime": True},
            issues=[],
            screenshot_names=["journey-01.png"],
        )

    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    result = await execute_run(run_id, store=store, team=FakeTeam())

    assert result.status == RunStatus.PASSED
    assert verifier_threads
    assert all(thread_id != event_loop_thread for thread_id in verifier_threads)


async def test_deterministic_failure_routes_to_bounded_technical_repair(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    def evidence(*args, **kwargs):
        calls["count"] += 1
        passed = calls["count"] != 1
        return DeterministicEvidence(passed=passed, checks={"runtime": passed}, issues=[] if passed else ["runtime failed"])
    monkeypatch.setattr("khalinos.workflow.verify_bundle", evidence)
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team)
    assert result.status == RunStatus.PASSED
    assert team.repairs == 1


async def test_third_failure_stops_instead_of_looping(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("khalinos.workflow.verify_bundle", lambda *args, **kwargs: DeterministicEvidence(passed=False, checks={"runtime": False}, issues=["same structural failure"]))
    store, run_id = setup_run(tmp_path)
    team = FakeTeam()
    result = await execute_run(run_id, store=store, team=team)
    assert result.status == RunStatus.BLOCKED
    assert team.repairs == 2
