from __future__ import annotations

import json
from pathlib import Path

from khalinos.models import ArtifactBundle, ArtifactFile
from khalinos.verification import materialize, verify_bundle


CRITERIA = [
    "Revealing a safe cell exposes multiple cells.",
    "The status exposes a completed runtime state.",
    "A flag expires after the bounded delay.",
    "Random behavior is reproducible under an approved seed.",
]


def contract_bundle(journeys: list[dict]) -> ArtifactBundle:
    files = {
        "index.html": """<!doctype html><html><head><link rel="stylesheet" href="styles.css"></head><body>
<button id="reveal" aria-label="Reveal cells">Reveal</button>
<button id="flag" aria-label="Toggle flag" aria-pressed="false">Flag</button>
<input id="safe" type="checkbox" checked aria-label="Safe mode">
<p id="status" class="ready pending" data-state="idle">Ready</p>
<p id="random"></p><div id="board"></div>
<script src="app.js" defer></script></body></html>""",
        "styles.css": "button{color:#fff;background:#222}.cell{display:inline-block}@media(max-width:600px){button{width:100%}}",
        "app.js": """
const board=document.querySelector('#board');
const status=document.querySelector('#status');
document.querySelector('#random').textContent=Math.random().toFixed(6);
document.querySelector('#reveal').addEventListener('click',()=>{
  board.innerHTML='<i class="cell revealed"></i><i class="cell revealed"></i><i class="cell revealed"></i>';
  status.textContent='Revealed 3'; status.dataset.state='complete';
  status.classList.remove('pending'); status.classList.add('done');
});
const flag=document.querySelector('#flag');
flag.addEventListener('click',()=>{
  flag.classList.add('flagged'); flag.setAttribute('aria-pressed','true');
  setTimeout(()=>{flag.classList.remove('flagged'); flag.setAttribute('aria-pressed','false'); status.textContent='Flag expired';},25);
});
""",
        "journey.json": json.dumps({"journeys": journeys}),
        "README.md": "# Runtime contract fixture\n\nA deterministic browser fixture.",
    }
    return ArtifactBundle(
        revision_summary="Exercise every approved typed runtime assertion.",
        files=[ArtifactFile(path=path, content=content) for path, content in files.items()],
    )


def complete_journeys() -> list[dict]:
    return [
        {
            "name": "safe reveal expands",
            "criterion": CRITERIA[0],
            "random_seed": 7,
            "steps": [
            {"assert_count": {"selector": ".cell.revealed", "operator": "eq", "value": 0}},
            {"click": "#reveal"},
            {"assert_count": {"selector": ".cell.revealed", "operator": "gte", "value": 3}},
            ],
        },
        {
            "name": "status exposes completion",
            "criterion": CRITERIA[1],
            "steps": [
            {"click": "#reveal"},
            {"assert_attribute": {"selector": "#status", "name": "data-state", "operator": "eq", "value": "complete"}},
            {"assert_class": {"selector": "#status", "includes": ["ready", "done"], "excludes": ["pending"]}},
            {"assert_state": {"selector": "#safe", "state": "checked"}},
            ],
        },
        {
            "name": "flag expires",
            "criterion": CRITERIA[2],
            "steps": [
            {"click": "#flag"},
            {"assert_class": {"selector": "#flag", "includes": ["flagged"], "excludes": []}},
            {"wait_ms": 40},
            {"assert_attribute": {"selector": "#flag", "name": "aria-pressed", "operator": "eq", "value": "false"}},
            {"assert_text": "Flag expired"},
            ],
        },
        {
            "name": "seeded random value",
            "criterion": CRITERIA[3],
            "random_seed": 7,
            "steps": [{"assert_text": "0.238781"}],
        },
    ]


def run_verification(tmp_path: Path, bundle: ArtifactBundle, criteria: list[str]):
    root = tmp_path / "product"
    materialize(bundle, root)
    return verify_bundle(bundle, root, tmp_path / "evidence", criteria)


def with_styles(bundle: ArtifactBundle, styles: str) -> ArtifactBundle:
    files = bundle.file_map()
    files["styles.css"] = styles
    return ArtifactBundle(
        revision_summary="A runtime responsive-layout fixture",
        files=[ArtifactFile(path=path, content=content) for path, content in files.items()],
    )


def test_intrinsic_responsive_layout_does_not_require_a_media_query(tmp_path: Path) -> None:
    artifact = with_styles(
        contract_bundle(complete_journeys()),
        "*{box-sizing:border-box}body{margin:0;padding:1rem}.cell{width:100%;max-width:20rem}button{max-width:100%}",
    )

    evidence = run_verification(tmp_path, artifact, CRITERIA)

    assert evidence.checks["responsive_layout"]
    assert evidence.passed


def test_mobile_overflow_fails_runtime_responsive_layout_check(tmp_path: Path) -> None:
    artifact = with_styles(
        contract_bundle(complete_journeys()),
        "body{margin:0;overflow:hidden}.cell{width:420px}button{width:400px}",
    )

    evidence = run_verification(tmp_path, artifact, CRITERIA)

    assert not evidence.checks["responsive_layout"]
    assert any("320px viewport" in issue for issue in evidence.issues)


def test_typed_journey_records_direct_evidence_for_every_criterion(tmp_path: Path) -> None:
    evidence = run_verification(tmp_path, contract_bundle(complete_journeys()), CRITERIA)

    assert evidence.passed
    assert evidence.checks["criterion_runtime_coverage"]
    assert set(evidence.criterion_evidence) == set(CRITERIA)
    assert all(items for items in evidence.criterion_evidence.values())
    assert any("observed=3" in item for item in evidence.criterion_evidence[CRITERIA[0]])
    assert any("seed=7" in item for item in evidence.criterion_evidence[CRITERIA[3]])


def test_claimed_pass_is_rejected_when_a_criterion_has_no_runtime_mapping(tmp_path: Path) -> None:
    journeys = complete_journeys()[:-1]

    evidence = run_verification(tmp_path, contract_bundle(journeys), CRITERIA)

    assert not evidence.passed
    assert not evidence.checks["criterion_runtime_coverage"]
    assert any("without direct runtime assertion evidence" in issue for issue in evidence.issues)


def test_wait_is_bounded_and_arbitrary_actions_are_rejected(tmp_path: Path) -> None:
    journey = complete_journeys()[0]
    journey["steps"] = [{"wait_ms": 12_001}, {"evaluate": "window.secret = true"}]

    evidence = run_verification(tmp_path, contract_bundle([journey]), CRITERIA)

    assert not evidence.passed
    assert any("wait_ms must be an integer" in issue for issue in evidence.issues)
