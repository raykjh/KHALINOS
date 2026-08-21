"""Execute both Godot fixtures and emit fixed-slot Agent–Capability traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import shutil
from pathlib import Path

from khalinos.agent_capability_receipts import (
    build_agent_capability_trace,
    compare_agent_capability_traces,
)
from khalinos.godot_gameplay import (
    GODOT_GAMEPLAY_SPRITE_PROFILE,
    compose_godot_gameplay_capabilities,
)
from khalinos.godot_side_scroll import (
    GODOT_SIDE_SCROLL_PROFILE,
    compose_godot_side_scroll_capabilities,
)


def _canonical_sha256(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ["KHALINOS_GODOT_EXECUTABLE"] = str(args.godot.resolve())

    repo = Path(__file__).resolve().parents[1]
    trinity_fixture = runpy.run_path(str(repo / "tests" / "test_godot_gameplay_toolpack.py"))
    side_fixture = runpy.run_path(str(repo / "tests" / "test_godot_side_scroll.py"))
    trinity = trinity_fixture["artifact"]()
    side_scroll = side_fixture["side_scroll_artifact"]()
    trinity_toolpack = trinity_fixture["GODOT_GAMEPLAY_TOOLPACK"]
    side_toolpack = side_fixture["GODOT_SIDE_SCROLL_TOOLPACK"]

    trinity_root = output / "trinity" / "product"
    trinity_evidence_root = output / "trinity" / "evidence"
    trinity_toolpack.execution_adapter.materialize(trinity, trinity_root)
    trinity_evidence = trinity_toolpack.evidence_adapter.verify(
        trinity,
        trinity_root,
        trinity_evidence_root,
        ["The top-down Trinity profile passes its approved mechanics and render checks."],
    )

    side_root = output / "side-scroll" / "product"
    side_evidence_root = output / "side-scroll" / "evidence"
    side_toolpack.execution_adapter.materialize(side_scroll, side_root)
    side_evidence = side_toolpack.evidence_adapter.verify(
        side_scroll,
        side_root,
        side_evidence_root,
        ["The side-scroll profile advances, auto-attacks, defeats enemies, and reaches its destination."],
    )
    if not trinity_evidence.passed or not side_evidence.passed:
        raise RuntimeError("both deterministic profile executions must pass before trace comparison")

    trinity_composition = compose_godot_gameplay_capabilities(
        trinity.gameplay, trinity.sprite_plan
    )
    side_composition = compose_godot_side_scroll_capabilities(side_scroll.plan)
    trinity_trace = build_agent_capability_trace(
        profile_id="godot.trinity-top-down",
        plan_sha256=trinity.plan_sha256,
        artifact_bundle_sha256=trinity.bundle_sha256,
        evidence_sha256=_canonical_sha256(trinity_evidence),
        composition=trinity_composition,
        profile=GODOT_GAMEPLAY_SPRITE_PROFILE,
        binary_sha256_by_path={
            trinity.asset.path: trinity.asset.sha256,
            trinity.sprite_atlas.path: trinity.sprite_atlas.sha256,
        },
    )
    side_trace = build_agent_capability_trace(
        profile_id="godot.side-scroll-destination",
        plan_sha256=side_scroll.plan_sha256,
        artifact_bundle_sha256=side_scroll.bundle_sha256,
        evidence_sha256=_canonical_sha256(side_evidence),
        composition=side_composition,
        profile=GODOT_SIDE_SCROLL_PROFILE,
        binary_sha256_by_path={side_scroll.asset.path: side_scroll.asset.sha256},
    )
    comparison = compare_agent_capability_traces(trinity_trace, side_trace)
    _write_json(output / "trinity-agent-capability-trace.json", trinity_trace)
    _write_json(output / "side-scroll-agent-capability-trace.json", side_trace)
    _write_json(output / "agent-capability-comparison.json", comparison)
    _write_json(output / "trinity-deterministic-evidence.json", trinity_evidence)
    _write_json(output / "side-scroll-deterministic-evidence.json", side_evidence)

    trinity_capture = trinity_evidence_root / trinity_evidence.screenshot_names[-1]
    side_capture = side_evidence_root / side_evidence.screenshot_names[-1]
    shutil.copy2(trinity_capture, output / "trinity-final.png")
    shutil.copy2(side_capture, output / "side-scroll-final.png")
    print(json.dumps({
        "passed": True,
        "fixed_max_agent_slots": comparison["fixed_max_agent_slots"],
        "trinity_active_agents": len(trinity_trace.active_agent_ids),
        "side_scroll_active_agents": len(side_trace.active_agent_ids),
        "new_agent_slots_created": comparison["new_agent_slots_created"],
        "trinity_trace_sha256": trinity_trace.sha256(),
        "side_scroll_trace_sha256": side_trace.sha256(),
        "comparison_sha256": _canonical_sha256(comparison),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
