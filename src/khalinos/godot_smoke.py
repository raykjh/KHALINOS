"""Isolated Cloud qualification entry point for the approved Godot ToolPack."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from khalinos.godot_topology import GodotRegion, GodotRegionKind, GodotTopologyPlan, compile_godot_topology
from khalinos.registry import APPROVED_TOOLPACKS


def main() -> int:
    binding = APPROVED_TOOLPACKS.binding_for("godot.topology")
    toolpack = APPROVED_TOOLPACKS.resolve(binding)
    plan = GodotTopologyPlan(
        project_name="KHALINOS Godot Qualification",
        initial_region="arrival",
        regions=(
            GodotRegion(region_id="arrival", label="Arrival", transitions=("workshop",)),
            GodotRegion(region_id="workshop", label="Workshop", transitions=("settings", "result")),
            GodotRegion(
                region_id="settings",
                label="Settings",
                kind=GodotRegionKind.OVERLAY,
                transitions=("result",),
            ),
            GodotRegion(region_id="result", label="Verified Result"),
        ),
    )
    artifact = compile_godot_topology(plan)
    criteria = [
        "Every declared region loads in the approved Godot runtime.",
        "The generated topology preserves the approved initial region and transitions.",
    ]
    with tempfile.TemporaryDirectory(prefix="khalinos-godot-cloud-") as temporary:
        root = Path(temporary)
        product = root / "product"
        evidence_dir = root / "evidence"
        toolpack.execution_adapter.materialize(artifact, product)
        evidence = toolpack.evidence_adapter.verify(
            artifact, product, evidence_dir, criteria
        )
        payload = {
            "schema_version": "khalinos-godot-toolpack-qualification-v1",
            "toolpack_binding": binding.model_dump(mode="json"),
            "plan_sha256": artifact.plan_sha256,
            "bundle_sha256": artifact.bundle_sha256,
            "materialized_files": sorted(artifact.files),
            "evidence": evidence.model_dump(mode="json"),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if evidence.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
