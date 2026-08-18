from __future__ import annotations

import json

import pytest

from khalinos.godot_toolpack import GODOT_TOPOLOGY_TOOLPACK
from khalinos.godot_topology import (
    CompiledGodotTopology,
    GodotRegion,
    GodotRegionKind,
    GodotTopologyPlan,
    compile_godot_topology,
)
from khalinos.registry import APPROVED_TOOLPACKS


def topology_plan() -> GodotTopologyPlan:
    return GodotTopologyPlan(
        project_name="Holdout Observatory",
        initial_region="arrival",
        regions=(
            GodotRegion(region_id="arrival", label="Arrival", transitions=("catalog",)),
            GodotRegion(region_id="catalog", label="Catalog", transitions=("workspace", "settings")),
            GodotRegion(region_id="settings", label="Settings", kind=GodotRegionKind.OVERLAY, transitions=("workspace",)),
            GodotRegion(region_id="workspace", label="Workspace"),
        ),
    )


def test_registry_resolves_exact_godot_toolpack_binding() -> None:
    binding = APPROVED_TOOLPACKS.binding_for("godot.topology")
    assert APPROVED_TOOLPACKS.resolve(binding) is GODOT_TOPOLOGY_TOOLPACK
    assert binding.version == "1.3.0"


def test_godot_plan_compiles_deterministically_and_materializes_only_declared_files(tmp_path) -> None:
    first = compile_godot_topology(topology_plan())
    second = compile_godot_topology(topology_plan())
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.files == second.files

    destination = tmp_path / "product"
    GODOT_TOPOLOGY_TOOLPACK.execution_adapter.materialize(first, destination)
    assert (destination / "project.godot").is_file()
    assert {item.name for item in (destination / "scenes").glob("*.tscn")} == {
        "arrival.tscn", "catalog.tscn", "settings.tscn", "workspace.tscn",
    }
    manifest = json.loads((destination / "KHALINOS_TOPOLOGY.json").read_text(encoding="utf-8"))
    assert manifest["initial_region"] == "arrival"


def test_godot_plan_rejects_unknown_or_unreachable_regions() -> None:
    with pytest.raises(ValueError, match="unknown"):
        GodotTopologyPlan(
            project_name="Broken Route",
            initial_region="start",
            regions=(
                GodotRegion(region_id="start", label="Start", transitions=("missing",)),
                GodotRegion(region_id="finish", label="Finish"),
            ),
        )
    with pytest.raises(ValueError, match="unreachable"):
        GodotTopologyPlan(
            project_name="Disconnected Route",
            initial_region="start",
            regions=(
                GodotRegion(region_id="start", label="Start"),
                GodotRegion(region_id="finish", label="Finish"),
            ),
        )


def test_godot_plan_rejects_model_authored_schema_version_changes() -> None:
    raw = topology_plan().model_dump(mode="json")
    raw["schema_version"] = "1.1.0"
    with pytest.raises(ValueError, match="khalinos-godot-topology-plan-v1"):
        GodotTopologyPlan.model_validate(raw)


def test_godot_materializer_refuses_to_overwrite_existing_product(tmp_path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "project.godot").write_text("user-owned\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        GODOT_TOPOLOGY_TOOLPACK.execution_adapter.materialize(
            compile_godot_topology(topology_plan()), destination
        )
    assert (destination / "project.godot").read_text(encoding="utf-8") == "user-owned\n"


def test_godot_toolpack_rejects_compiled_bundle_tampering(tmp_path) -> None:
    artifact = compile_godot_topology(topology_plan())
    changed = dict(artifact.files)
    changed["project.godot"] += "\n# changed after approval\n"
    tampered = CompiledGodotTopology(
        plan=artifact.plan,
        plan_sha256=artifact.plan_sha256,
        bundle_sha256=artifact.bundle_sha256,
        files=changed,
    )
    with pytest.raises(PermissionError, match="bundle digest changed"):
        GODOT_TOPOLOGY_TOOLPACK.execution_adapter.materialize(tampered, tmp_path / "product")


def test_godot_evidence_rejects_materialized_file_swap(tmp_path, monkeypatch) -> None:
    executable = r"E:\memory R data\archive_20260818_first_priority\C-tmp\khalinos-engine-bakeoff\godot\Godot_v4.7.1-stable_win64.exe"
    monkeypatch.setenv("KHALINOS_GODOT_EXECUTABLE", executable)
    artifact = compile_godot_topology(topology_plan())
    product = tmp_path / "product"
    GODOT_TOPOLOGY_TOOLPACK.execution_adapter.materialize(artifact, product)
    (product / "project.godot").write_text("swapped\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="changed after approval"):
        GODOT_TOPOLOGY_TOOLPACK.evidence_adapter.verify(
            artifact, product, tmp_path / "evidence", ["Every region loads."],
        )


def test_real_godot_headless_vertical_path(tmp_path, monkeypatch) -> None:
    executable = r"E:\memory R data\archive_20260818_first_priority\C-tmp\khalinos-engine-bakeoff\godot\Godot_v4.7.1-stable_win64.exe"
    monkeypatch.setenv("KHALINOS_GODOT_EXECUTABLE", executable)
    artifact = compile_godot_topology(topology_plan())
    product = tmp_path / "product"
    evidence = tmp_path / "evidence"
    GODOT_TOPOLOGY_TOOLPACK.execution_adapter.materialize(artifact, product)
    receipt = GODOT_TOPOLOGY_TOOLPACK.evidence_adapter.verify(
        artifact,
        product,
        evidence,
        ["Every declared region loads in the approved Godot runtime."],
    )
    assert receipt.passed is True
    assert all(receipt.checks.values())
    assert (evidence / "godot-topology-probe.json").is_file()
