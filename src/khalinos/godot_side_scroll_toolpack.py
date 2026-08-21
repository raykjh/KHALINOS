"""Execution and evidence boundary for the experimental Godot side-scroll profile."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from uuid import uuid4

from khalinos.godot_side_scroll import CompiledGodotSideScroll
from khalinos.godot_toolpack import APPROVED_GODOT_RUNTIMES
from khalinos.godot_visual_toolpack import _start_xvfb
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
from khalinos.visual_assets import ASSET_PATH, png_dimensions


SIDE_SCROLL_PATHS = {
    "KHALINOS_DESTINATION.json",
    "KHALINOS_SIDE_SCROLL.json",
    "README.md",
    "project.godot",
    "scenes/gameplay.tscn",
    "scripts/khalinos_side_scroll.gd",
    "scripts/khalinos_side_scroll_probe.gd",
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


def _validate_artifact(artifact: CompiledGodotSideScroll) -> None:
    if set(artifact.files) != SIDE_SCROLL_PATHS:
        raise PermissionError("Godot side-scroll artifact exceeds its declared output surface")
    if artifact.asset.path != ASSET_PATH or artifact.asset.media_type != "image/png":
        raise PermissionError("Godot side-scroll artifact contains an unapproved binary asset")
    if hashlib.sha256(artifact.asset.bytes()).hexdigest() != artifact.asset.sha256:
        raise PermissionError("Godot side-scroll visual asset digest changed after approval")
    plan_sha = _canonical_sha256({
        "plan": artifact.plan.model_dump(mode="json"),
        "concept": artifact.concept.model_dump(mode="json"),
        "asset_sha256": artifact.asset.sha256,
    })
    if artifact.plan_sha256 != plan_sha:
        raise PermissionError("Godot side-scroll plan digest changed after compilation")
    bundle_sha = _canonical_sha256({
        "plan_sha256": plan_sha,
        "files": artifact.files,
        "asset_sha256": artifact.asset.sha256,
    })
    if artifact.bundle_sha256 != bundle_sha:
        raise PermissionError("Godot side-scroll bundle digest changed after compilation")
    total = sum(len(item.encode("utf-8")) for item in artifact.files.values()) + len(artifact.asset.bytes())
    if len(artifact.files) + 1 > GODOT_SIDE_SCROLL_MANIFEST.output.max_file_count:
        raise PermissionError("Godot side-scroll artifact exceeds its file-count limit")
    if total > GODOT_SIDE_SCROLL_MANIFEST.output.max_total_bytes:
        raise PermissionError("Godot side-scroll artifact exceeds its byte limit")


def _validate_materialized(artifact: CompiledGodotSideScroll, root: Path) -> None:
    destination = root.resolve()
    for raw_path, expected in artifact.files.items():
        target = (destination / Path(*PurePosixPath(raw_path).parts)).resolve()
        if not target.is_relative_to(destination) or not target.is_file():
            raise PermissionError(f"materialized Godot side-scroll file is missing: {raw_path}")
        if target.read_text(encoding="utf-8") != expected:
            raise PermissionError(f"materialized Godot side-scroll file changed after approval: {raw_path}")
    asset = (destination / Path(*PurePosixPath(artifact.asset.path).parts)).resolve()
    if not asset.is_file() or _file_sha256(asset) != artifact.asset.sha256:
        raise PermissionError("materialized Godot side-scroll visual asset changed after approval")


class GodotSideScrollExecutionAdapter:
    adapter_id = "godot.side-scroll.execution.v1"

    def materialize(self, artifact: CompiledGodotSideScroll, root: Path) -> None:
        _validate_artifact(artifact)
        destination = root.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        staging = destination / f".khalinos-godot-side-scroll-{uuid4().hex}"
        written: list[Path] = []
        payloads = {
            **{path: content.encode("utf-8") for path, content in artifact.files.items()},
            artifact.asset.path: artifact.asset.bytes(),
        }
        try:
            for raw_path, payload in payloads.items():
                relative = PurePosixPath(raw_path)
                target = (destination / Path(*relative.parts)).resolve()
                if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(destination):
                    raise PermissionError("Godot side-scroll artifact contains an unsafe output path")
                if target.exists() and target.read_bytes() != payload:
                    raise FileExistsError(f"Godot side-scroll ToolPack refuses to overwrite {raw_path}")
                staged = staging / Path(*relative.parts)
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(payload)
            for raw_path in payloads:
                target = destination / Path(*PurePosixPath(raw_path).parts)
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / Path(*PurePosixPath(raw_path).parts), target)
                written.append(target)
        except Exception:
            for target in reversed(written):
                target.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        _validate_materialized(artifact, destination)


class GodotSideScrollEvidenceAdapter:
    adapter_id = "godot.side-scroll.evidence.v1"

    def verify(
        self,
        artifact: CompiledGodotSideScroll,
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
        if (executable.stat().st_size, executable_sha256) not in APPROVED_GODOT_RUNTIMES:
            raise PermissionError("Godot executable size or digest changed after approval")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        imported = subprocess.run(
            [str(executable), "--language", "en", "--headless",
             "--log-file", str((evidence_dir / "side-scroll-import.log").resolve()),
             "--path", str(root.resolve()), "--editor", "--quit"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        receipt_path = evidence_dir / "side-scroll-probe.json"
        probe = subprocess.run(
            [str(executable), "--language", "en", "--headless",
             "--log-file", str((evidence_dir / "side-scroll-probe.log").resolve()),
             "--path", str(root.resolve()),
             "--script", "res://scripts/khalinos_side_scroll_probe.gd", "--",
             f"--output={receipt_path.resolve()}"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        xvfb, environment = _start_xvfb(artifact.plan.viewport_width, artifact.plan.viewport_height)
        try:
            prefix = evidence_dir / "side-scroll-render.png"
            rendered = subprocess.run(
                [str(executable), "--language", "en", "--windowed",
                 "--log-file", str((evidence_dir / "side-scroll-render.log").resolve()),
                 "--path", str(root.resolve()), "--write-movie", str(prefix.resolve()),
                 "--fixed-fps", "30", "--quit-after", "90"],
                cwd=root, env=environment, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60, shell=False, check=False,
            )
        finally:
            if xvfb is not None:
                xvfb.terminate()
                try:
                    xvfb.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    xvfb.kill()
        frames = sorted(evidence_dir.glob("side-scroll-render????????.png"))
        capture = frames[-1] if frames else prefix
        dimensions = png_dimensions(capture.read_bytes()) if capture.is_file() else (0, 0)
        checks = {
            "approved_executable_digest": True,
            "asset_import_process": imported.returncode == 0,
            "headless_process": probe.returncode == 0,
            "probe_schema": receipt.get("schema_version") == "khalinos-godot-side-scroll-probe-v1",
            "horizontal_lane_present": receipt.get("horizontal_lane_present") is True,
            "movement_right": receipt.get("movement_right") is True,
            "enemy_spawned": receipt.get("enemy_spawned") is True,
            "auto_attack_fired": receipt.get("auto_attack_fired") is True,
            "enemy_defeated": receipt.get("enemy_defeated") is True,
            "destination_reached": receipt.get("destination_reached") is True,
            "victory": receipt.get("victory") is True,
            "probe_passed": receipt.get("passed") is True,
            "trusted_asset_materialized": _file_sha256(root / ASSET_PATH) == artifact.asset.sha256,
            "display_render_process": rendered.returncode == 0,
            "display_render_frames": len(frames) == 90,
            "display_render_dimensions": dimensions == (artifact.plan.viewport_width, artifact.plan.viewport_height),
            "display_render_nontrivial": capture.is_file() and capture.stat().st_size > 5_000,
        }
        issues = [name for name, passed in checks.items() if not passed]
        observation = (
            "The approved Godot runtime exercised a horizontal lane, continuous rightward progress, "
            "enemy spawning, visible automatic attacks, enemy defeat, and destination victory; "
            f"the display runtime produced {len(frames)} {dimensions[0]}x{dimensions[1]} PNG frames."
        )
        return DeterministicEvidence(
            passed=not issues,
            checks=checks,
            issues=issues,
            screenshot_names=[capture.name] if capture.is_file() else [],
            criterion_evidence={criterion: [observation] for criterion in acceptance_criteria},
        )


GODOT_SIDE_SCROLL_IMPLEMENTATION_SOURCES = (
    "godot_capability_packs.py",
    "godot_side_scroll.py",
    "godot_side_scroll_toolpack.py",
    "toolpacks.py",
    "visual_assets.py",
)

GODOT_SIDE_SCROLL_MANIFEST = ToolPackManifest(
    toolpack_id="godot.side-scroll-experiment",
    version="0.1.1",
    display_name="Godot Side-scroll Composition Experiment",
    description="Composes a bounded horizontal auto-combat journey from reusable Godot Capability Packs and verifies mechanics in the approved runtime.",
    implementation_sha256=source_set_sha256(Path(__file__).parent, GODOT_SIDE_SCROLL_IMPLEMENTATION_SOURCES),
    execution_adapter_id=GodotSideScrollExecutionAdapter.adapter_id,
    project_kinds=("godot",),
    work_modes=("composition_experiment",),
    capabilities=(
        CapabilityDeclaration(
            capability_id="godot.side-scroll.control",
            operations=("build",),
            scopes=("artifact:write", "godot:scene", "godot:script"),
        ),
        CapabilityDeclaration(
            capability_id="godot.side-scroll.evidence",
            operations=("execute", "observe"),
            scopes=("runtime:display", "runtime:headless"),
        ),
    ),
    routing=RoutingContract(
        primary_project_kind="godot",
        supported_outcomes=("bounded side-scrolling auto-combat destination journeys",),
        excluded_outcomes=("arbitrary platformers multiplayer or production-ready games",),
        selection_guidance="Use only to test the approved side-scroll composition profile, not as a general Godot fallback.",
    ),
    output=OutputContract(
        artifact_kind="godot.side-scroll-experiment",
        authorized_paths=tuple(sorted(SIDE_SCROLL_PATHS | {ASSET_PATH})),
        max_file_count=8,
        max_total_bytes=5_000_000,
    ),
    evidence=EvidenceContract(
        adapter_id=GodotSideScrollEvidenceAdapter.adapter_id,
        evidence_types=(
            "gameplay.auto-attack",
            "gameplay.destination",
            "gameplay.horizontal-progress",
            "godot.display.render",
            "runtime.assertion",
            "runtime.screenshot",
        ),
        network_isolated=True,
        independent_verifier_required=True,
    ),
)

GODOT_SIDE_SCROLL_TOOLPACK = RegisteredToolPack[
    CompiledGodotSideScroll, DeterministicEvidence
](
    manifest=GODOT_SIDE_SCROLL_MANIFEST,
    execution_adapter=GodotSideScrollExecutionAdapter(),
    evidence_adapter=GodotSideScrollEvidenceAdapter(),
)
