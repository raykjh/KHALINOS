"""Approved Nano Banana assisted Godot visual-prototype ToolPack."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path, PurePosixPath
from uuid import uuid4

from khalinos.godot_toolpack import APPROVED_GODOT_RUNTIMES
from khalinos.godot_visual import CompiledGodotVisualPrototype
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


CORE_PATHS = {
    "project.godot",
    "KHALINOS_TOPOLOGY.json",
    "KHALINOS_VISUAL_PROTOTYPE.json",
    "scripts/khalinos_topology_region.gd",
    "scripts/khalinos_topology_probe.gd",
    "scripts/khalinos_visual_probe.gd",
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


def _validate_artifact(artifact: CompiledGodotVisualPrototype) -> None:
    actual = set(artifact.files)
    expected_scenes = {f"scenes/{item.region_id}.tscn" for item in artifact.topology.regions}
    if actual != CORE_PATHS | expected_scenes:
        raise PermissionError("Godot visual artifact exceeds its declared output surface")
    if artifact.asset.path != ASSET_PATH or artifact.asset.media_type != "image/png":
        raise PermissionError("Godot visual artifact contains an unapproved binary asset")
    if hashlib.sha256(artifact.asset.bytes()).hexdigest() != artifact.asset.sha256:
        raise PermissionError("Godot visual asset digest changed after approval")
    plan_sha = _canonical_sha256({
        "topology": artifact.topology.model_dump(mode="json"),
        "concept": artifact.concept.model_dump(mode="json"),
        "asset_sha256": artifact.asset.sha256,
    })
    if artifact.plan_sha256 != plan_sha:
        raise PermissionError("Godot visual plan digest changed after compilation")
    expected_bundle = _canonical_sha256({
        "plan_sha256": plan_sha,
        "files": artifact.files,
        "asset_sha256": artifact.asset.sha256,
    })
    if artifact.bundle_sha256 != expected_bundle:
        raise PermissionError("Godot visual bundle digest changed after compilation")
    total = sum(len(value.encode("utf-8")) for value in artifact.files.values()) + len(artifact.asset.bytes())
    if len(actual) + 1 > GODOT_VISUAL_PROTOTYPE_MANIFEST.output.max_file_count:
        raise PermissionError("Godot visual artifact exceeds its file-count limit")
    if total > GODOT_VISUAL_PROTOTYPE_MANIFEST.output.max_total_bytes:
        raise PermissionError("Godot visual artifact exceeds its byte limit")


def _validate_materialized(artifact: CompiledGodotVisualPrototype, root: Path) -> None:
    destination = root.resolve()
    for raw_path, expected in artifact.files.items():
        target = (destination / Path(*PurePosixPath(raw_path).parts)).resolve()
        if not target.is_relative_to(destination) or not target.is_file():
            raise PermissionError(f"materialized Godot file is missing: {raw_path}")
        if target.read_text(encoding="utf-8") != expected:
            raise PermissionError(f"materialized Godot file changed after approval: {raw_path}")
    asset = (destination / Path(*PurePosixPath(artifact.asset.path).parts)).resolve()
    if not asset.is_file() or _file_sha256(asset) != artifact.asset.sha256:
        raise PermissionError("materialized Godot visual asset changed after approval")


class GodotVisualExecutionAdapter:
    adapter_id = "godot.visual-prototype.execution.v1"

    def materialize(self, artifact: CompiledGodotVisualPrototype, root: Path) -> None:
        _validate_artifact(artifact)
        destination = root.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        staging = destination / f".khalinos-godot-visual-{uuid4().hex}"
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
                    raise PermissionError("Godot visual artifact contains an unsafe output path")
                if target.exists() and target.read_bytes() != payload:
                    raise FileExistsError(f"Godot visual ToolPack refuses to overwrite {raw_path}")
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


def _start_xvfb(width: int, height: int) -> tuple[subprocess.Popen[bytes] | None, dict[str, str]]:
    environment = dict(os.environ)
    if os.name == "nt":
        return None, environment
    executable = shutil.which("Xvfb")
    if not executable:
        raise PermissionError("approved Xvfb display runtime is unavailable")
    for display_number in range(90, 120):
        socket = Path(f"/tmp/.X11-unix/X{display_number}")
        if socket.exists():
            continue
        process = subprocess.Popen(
            [executable, f":{display_number}", "-screen", "0", f"{width}x{height}x24", "-nolisten", "tcp", "-ac"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for _ in range(50):
            if process.poll() is not None:
                detail = (process.stderr.read() if process.stderr else b"").decode("utf-8", errors="replace")
                raise RuntimeError(f"Xvfb exited before display readiness: {detail}")
            if socket.exists():
                environment["DISPLAY"] = f":{display_number}"
                return process, environment
            time.sleep(0.1)
        process.terminate()
        process.wait(timeout=5)
        raise TimeoutError("Xvfb display did not become ready within 5 seconds")
    raise RuntimeError("no isolated Xvfb display number is available")


class GodotVisualEvidenceAdapter:
    adapter_id = "godot.visual-prototype.evidence.v1"

    def verify(
        self,
        artifact: CompiledGodotVisualPrototype,
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
            [str(executable), "--language", "en", "--headless", "--path", str(root.resolve()), "--editor", "--quit"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        receipt_path = evidence_dir / "godot-topology-probe.json"
        probe = subprocess.run(
            [str(executable), "--language", "en", "--headless", "--path", str(root.resolve()),
             "--script", "res://scripts/khalinos_topology_probe.gd", "--", f"--output={receipt_path.resolve()}"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        expected = [item.region_id for item in artifact.topology.regions]
        visual_receipt_path = evidence_dir / "godot-visual-probe.json"
        visual_probe = subprocess.run(
            [str(executable), "--language", "en", "--headless", "--path", str(root.resolve()),
             "--script", "res://scripts/khalinos_visual_probe.gd", "--", f"--output={visual_receipt_path.resolve()}"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        visual_receipt = json.loads(
            visual_receipt_path.read_text(encoding="utf-8")
        ) if visual_receipt_path.is_file() else {}
        xvfb, environment = _start_xvfb(artifact.topology.viewport_width, artifact.topology.viewport_height)
        try:
            prefix = evidence_dir / "godot-render.png"
            rendered = subprocess.run(
                [str(executable), "--language", "en", "--windowed", "--path", str(root.resolve()),
                 "--write-movie", str(prefix.resolve()), "--fixed-fps", "30", "--quit-after", "3"],
                cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=60, shell=False, check=False,
            )
        finally:
            if xvfb is not None:
                xvfb.terminate()
                try:
                    xvfb.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    xvfb.kill()
        frames = sorted(evidence_dir.glob("godot-render????????.png"))
        capture = frames[-1] if frames else prefix
        dimensions = png_dimensions(capture.read_bytes()) if capture.is_file() else (0, 0)
        checks = {
            "approved_executable_digest": True,
            "asset_import_process": imported.returncode == 0,
            "headless_process": probe.returncode == 0,
            "all_regions_loaded": receipt.get("visited") == expected,
            "probe_error_free": receipt.get("errors") == [],
            "visual_probe_process": visual_probe.returncode == 0,
            "visual_texture_ready": visual_receipt.get("texture_ready") is True,
            "visual_scrim_translucent": visual_receipt.get("scrim_translucent") is True,
            "trusted_asset_materialized": _file_sha256(root / ASSET_PATH) == artifact.asset.sha256,
            "display_render_process": rendered.returncode == 0,
            "display_render_frames": len(frames) == 3,
            "display_render_dimensions": dimensions == (artifact.topology.viewport_width, artifact.topology.viewport_height),
            "display_render_nontrivial": capture.is_file() and capture.stat().st_size > 10_000,
        }
        issues = [name for name, passed in checks.items() if not passed]
        observation = (
            f"Godot loaded {len(receipt.get('visited', []))}/{len(expected)} regions and produced "
            f"{len(frames)} display-backed {dimensions[0]}x{dimensions[1]} PNG frames with asset sha256={artifact.asset.sha256}."
        )
        return DeterministicEvidence(
            passed=not issues,
            checks=checks,
            issues=issues,
            screenshot_names=[capture.name] if capture.is_file() else [],
            criterion_evidence={criterion: [observation] for criterion in acceptance_criteria},
        )


GODOT_VISUAL_IMPLEMENTATION_SOURCES = (
    "agents.py", "godot_topology.py", "godot_visual.py", "godot_visual_toolpack.py",
    "godot_visual_workflow.py", "run_router.py", "visual_assets.py",
)

GODOT_VISUAL_PROTOTYPE_MANIFEST = ToolPackManifest(
    toolpack_id="godot.visual-prototype",
    version="1.0.0",
    display_name="Godot Visual Prototype ToolPack",
    description="Generates bounded Nano Banana visual foundations, compiles them into trusted Godot topology, and selects from real rendered evidence.",
    implementation_sha256=source_set_sha256(Path(__file__).parent, GODOT_VISUAL_IMPLEMENTATION_SOURCES),
    execution_adapter_id=GodotVisualExecutionAdapter.adapter_id,
    project_kinds=("godot",),
    work_modes=("new_product_build",),
    capabilities=(
        CapabilityDeclaration(capability_id="godot.visual.asset", operations=("generate", "observe"), scopes=("artifact:write", "model:image")),
        CapabilityDeclaration(capability_id="godot.visual.control", operations=("build",), scopes=("artifact:write", "godot:scene")),
        CapabilityDeclaration(capability_id="godot.visual.evidence", operations=("execute", "observe"), scopes=("runtime:display", "runtime:headless")),
    ),
    routing=RoutingContract(
        primary_project_kind="godot",
        supported_outcomes=(
            "presentation-ready Godot visual and screen-flow prototypes",
            "three Nano Banana visual candidates selected from real Godot renders",
        ),
        excluded_outcomes=(
            "finished gameplay mechanics physics animation or production-ready game",
            "repair of existing Godot projects or arbitrary scripts and assets",
        ),
        selection_guidance="Choose this route when visual direction and navigable Godot screen structure must be established before gameplay implementation.",
    ),
    output=OutputContract(
        artifact_kind="godot.visual-prototype-project",
        authorized_paths=("KHALINOS_TOPOLOGY.json", "KHALINOS_VISUAL_PROTOTYPE.json", "assets/visual-foundation.png", "project.godot", "scenes/*.tscn", "scripts/khalinos_topology_probe.gd", "scripts/khalinos_topology_region.gd", "scripts/khalinos_visual_probe.gd"),
        max_file_count=25,
        max_total_bytes=2_800_000,
    ),
    evidence=EvidenceContract(
        adapter_id=GodotVisualEvidenceAdapter.adapter_id,
        evidence_types=("godot.display.render", "godot.headless.probe", "runtime.screenshot", "visual.asset.loaded"),
        network_isolated=False,
        independent_verifier_required=True,
    ),
)

GODOT_VISUAL_PROTOTYPE_TOOLPACK = RegisteredToolPack[
    CompiledGodotVisualPrototype, DeterministicEvidence
](
    manifest=GODOT_VISUAL_PROTOTYPE_MANIFEST,
    execution_adapter=GodotVisualExecutionAdapter(),
    evidence_adapter=GodotVisualEvidenceAdapter(),
)
