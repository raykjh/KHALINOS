"""Qualify the separate Godot visual-prototype ToolPack with a trusted PNG."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from khalinos.godot_topology import GodotRegion, GodotTopologyPlan
from khalinos.godot_visual import compile_godot_visual_prototype
from khalinos.godot_visual_toolpack import GODOT_VISUAL_PROTOTYPE_TOOLPACK
from khalinos.models import VisualConcept
from khalinos.visual_assets import trusted_png_asset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if root.exists():
        raise FileExistsError(f"output root already exists: {root}")
    os.environ["KHALINOS_GODOT_EXECUTABLE"] = str(args.godot.resolve())
    topology = GodotTopologyPlan(
        project_name="The Threefold Passage",
        initial_region="arrival",
        regions=(
            GodotRegion(region_id="arrival", label="The Threefold Passage", transitions=("route_map",)),
            GodotRegion(region_id="route_map", label="Choose the Safe Route", transitions=("verified_exit",)),
            GodotRegion(region_id="verified_exit", label="Verified Exit"),
        ),
    )
    concept = VisualConcept(
        candidate_id="V1",
        name="Luminous Cavern Route",
        design_thesis="A cinematic ancient cavern makes route selection feel physical while keeping the decision surface restrained.",
        composition="A broad environmental field supports a centered route title and a short vertical sequence of actions.",
        typography="Large restrained headings and compact labels preserve readability over the atmospheric image.",
        palette=["midnight blue", "weathered bronze", "mineral cyan", "warm parchment"],
        interaction_emphasis="The current route action is the brightest controlled element while the environment remains supporting context.",
        anti_goals=["generic dashboard grid", "text embedded in generated imagery", "ornamental clutter"],
    )
    artifact = compile_godot_visual_prototype(
        topology,
        concept,
        trusted_png_asset(args.asset.read_bytes()),
    )
    product = root / "product"
    evidence = root / "evidence"
    GODOT_VISUAL_PROTOTYPE_TOOLPACK.execution_adapter.materialize(artifact, product)
    receipt = GODOT_VISUAL_PROTOTYPE_TOOLPACK.evidence_adapter.verify(
        artifact,
        product,
        evidence,
        ["The visual direction is visible in a real Godot render."],
    )
    report = {
        "artifact_plan_sha256": artifact.plan_sha256,
        "artifact_bundle_sha256": artifact.bundle_sha256,
        "asset_sha256": artifact.asset.sha256,
        "evidence": receipt.model_dump(mode="json"),
    }
    (root / "qualification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if receipt.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
