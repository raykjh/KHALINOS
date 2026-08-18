"""Approved Godot topology ToolPack and its trusted host adapters."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from uuid import uuid4

from khalinos.godot_topology import CompiledGodotTopology
from khalinos.models import DeterministicEvidence
from khalinos.toolpacks import (
    CapabilityDeclaration,
    EvidenceContract,
    OutputContract,
    RegisteredToolPack,
    RoutingContract,
    ToolPackManifest,
    source_set_sha256,
)


APPROVED_GODOT_RUNTIMES = {
    # Official Godot 4.7.1 Windows x86_64 executable preserved from the engine bakeoff.
    (178_997_256, "323f9c4cc5db674e98815cdd8e69da007d5efc779abedc8c0e42883b7fdea12a"),
    # Official Godot 4.7.1 Linux x86_64 executable from the release asset whose
    # ZIP sha256 is c7ff14fd28472c8d4f193043de30278dcf7e5241a1dcf7566b02e27addaa33ba.
    (144_583_504, "32f8d7596c4b41185512b1c49d69f2da3be018fd784a53e349fa92a98a97bcde"),
}
CORE_PATHS = {
    "project.godot",
    "KHALINOS_TOPOLOGY.json",
    "scripts/khalinos_topology_region.gd",
    "scripts/khalinos_topology_probe.gd",
}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_artifact(artifact: CompiledGodotTopology) -> None:
    actual = set(artifact.files)
    scenes = actual - CORE_PATHS
    expected_scenes = {f"scenes/{item.region_id}.tscn" for item in artifact.plan.regions}
    if scenes != expected_scenes or not CORE_PATHS.issubset(actual):
        raise PermissionError("Godot artifact exceeds its declared topology output surface")
    if len(actual) > GODOT_TOPOLOGY_MANIFEST.output.max_file_count:
        raise PermissionError("Godot artifact exceeds its file-count limit")
    if sum(len(value.encode("utf-8")) for value in artifact.files.values()) > GODOT_TOPOLOGY_MANIFEST.output.max_total_bytes:
        raise PermissionError("Godot artifact exceeds its byte limit")
    if artifact.plan_sha256 != _canonical_sha256(artifact.plan):
        raise PermissionError("Godot topology plan digest changed after compilation")
    expected_bundle = _canonical_sha256({
        "plan_sha256": artifact.plan_sha256,
        "files": artifact.files,
    })
    if artifact.bundle_sha256 != expected_bundle:
        raise PermissionError("Godot topology bundle digest changed after compilation")


def _validate_materialized(artifact: CompiledGodotTopology, root: Path) -> None:
    destination = root.resolve()
    for raw_path, expected in artifact.files.items():
        relative = PurePosixPath(raw_path)
        target = (destination / Path(*relative.parts)).resolve()
        if not target.is_relative_to(destination) or not target.is_file():
            raise PermissionError(f"materialized Godot file is missing: {raw_path}")
        if target.read_text(encoding="utf-8") != expected:
            raise PermissionError(f"materialized Godot file changed after approval: {raw_path}")


class GodotTopologyExecutionAdapter:
    adapter_id = "godot.topology.execution.v1"

    def materialize(self, artifact: CompiledGodotTopology, root: Path) -> None:
        _validate_artifact(artifact)
        destination = root.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        targets: list[tuple[Path, str]] = []
        for raw_path, content in artifact.files.items():
            relative = PurePosixPath(raw_path)
            target = (destination / Path(*relative.parts)).resolve()
            if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(destination):
                raise PermissionError("Godot artifact contains an unsafe output path")
            if target.exists() and target.read_text(encoding="utf-8") != content:
                raise FileExistsError(f"Godot ToolPack refuses to overwrite {raw_path}")
            targets.append((target, content))
        staging = destination / f".khalinos-godot-{uuid4().hex}"
        written: list[Path] = []
        try:
            for target, content in targets:
                relative = target.relative_to(destination)
                staged = staging / relative
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_text(content, encoding="utf-8", newline="\n")
            for target, _content in targets:
                if target.exists():
                    continue
                relative = target.relative_to(destination)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / relative, target)
                written.append(target)
        except Exception:
            for target in reversed(written):
                target.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        _validate_materialized(artifact, destination)


class GodotHeadlessEvidenceAdapter:
    adapter_id = "godot.headless.evidence.v1"

    def verify(
        self,
        artifact: CompiledGodotTopology,
        root: Path,
        evidence_dir: Path,
        acceptance_criteria: list[str],
    ) -> DeterministicEvidence:
        _validate_artifact(artifact)
        _validate_materialized(artifact, root)
        executable = Path(os.environ.get("KHALINOS_GODOT_EXECUTABLE", "")).resolve()
        if not executable.is_file():
            raise PermissionError("approved Godot executable is unavailable")
        executable_sha256 = _file_sha256(executable)
        runtime_binding = (executable.stat().st_size, executable_sha256)
        if runtime_binding not in APPROVED_GODOT_RUNTIMES:
            raise PermissionError("Godot executable size or digest changed after approval")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = (evidence_dir / "godot-topology-probe.json").resolve()
        argv = [
            str(executable), "--language", "en", "--headless", "--path", str(root.resolve()),
            "--script", "res://scripts/khalinos_topology_probe.gd", "--", f"--output={receipt_path}",
        ]
        completed = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            shell=False,
            check=False,
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        expected = [item.region_id for item in artifact.plan.regions]
        checks = {
            "approved_executable_digest": True,
            "headless_process": completed.returncode == 0,
            "probe_schema": receipt.get("schema_version") == "khalinos-godot-topology-probe-v1",
            "all_regions_loaded": receipt.get("visited") == expected,
            "probe_error_free": receipt.get("errors") == [],
            "probe_passed": receipt.get("passed") is True,
        }
        issues = [name for name, passed in checks.items() if not passed]
        observation = (
            f"Godot headless probe loaded {len(receipt.get('visited', []))}/{len(expected)} declared regions; "
            f"executable sha256={executable_sha256}."
        )
        return DeterministicEvidence(
            passed=not issues,
            checks=checks,
            issues=issues,
            criterion_evidence={criterion: [observation] for criterion in acceptance_criteria},
        )


GODOT_IMPLEMENTATION_SOURCES = (
    "agents.py",
    "godot_toolpack.py",
    "godot_topology.py",
    "godot_workflow.py",
    "run_router.py",
)

GODOT_TOPOLOGY_MANIFEST = ToolPackManifest(
    toolpack_id="godot.topology",
    version="1.3.0",
    display_name="Godot Topology ToolPack",
    description="Compiles bounded screen topology plans and proves every generated scene with a digest-bound Godot headless runtime.",
    implementation_sha256=source_set_sha256(Path(__file__).parent, GODOT_IMPLEMENTATION_SOURCES),
    execution_adapter_id=GodotTopologyExecutionAdapter.adapter_id,
    project_kinds=("godot",),
    work_modes=("new_product_build",),
    capabilities=(
        CapabilityDeclaration(
            capability_id="godot.topology.control",
            operations=("build",),
            scopes=("artifact:write", "godot:scene"),
        ),
        CapabilityDeclaration(
            capability_id="godot.topology.evidence",
            operations=("execute", "observe"),
            scopes=("runtime:headless",),
        ),
    ),
    routing=RoutingContract(
        primary_project_kind="godot",
        supported_outcomes=(
            "bounded Godot screen and overlay topology prototypes",
            "deterministic scene loading and declared navigation proof",
        ),
        excluded_outcomes=(
            "arbitrary scripts or external assets",
            "gameplay mechanics physics animation and production art",
            "repair of existing Godot projects",
        ),
        selection_guidance="Choose this route only when connected Godot screens and overlays are the outcome, rather than a finished playable game.",
    ),
    output=OutputContract(
        artifact_kind="godot.topology-project",
        authorized_paths=("KHALINOS_TOPOLOGY.json", "project.godot", "scenes/*.tscn", "scripts/khalinos_topology_probe.gd", "scripts/khalinos_topology_region.gd"),
        max_file_count=20,
        max_total_bytes=250_000,
    ),
    evidence=EvidenceContract(
        adapter_id=GodotHeadlessEvidenceAdapter.adapter_id,
        evidence_types=("godot.headless.probe", "runtime.assertion"),
        network_isolated=False,
        independent_verifier_required=True,
    ),
)

GODOT_TOPOLOGY_TOOLPACK = RegisteredToolPack[
    CompiledGodotTopology, DeterministicEvidence
](
    manifest=GODOT_TOPOLOGY_MANIFEST,
    execution_adapter=GodotTopologyExecutionAdapter(),
    evidence_adapter=GodotHeadlessEvidenceAdapter(),
)
