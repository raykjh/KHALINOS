"""Approved asset-assisted Godot 2D Gameplay Vertical Slice ToolPack."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from uuid import uuid4

from khalinos.godot_gameplay import CompiledGodotGameplay
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


CORE_PATHS = {
    "project.godot", "KHALINOS_GAMEPLAY.json", "README.md",
    "scenes/gameplay.tscn", "scripts/khalinos_gameplay.gd",
    "scripts/khalinos_gameplay_probe.gd",
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


def _validate_artifact(artifact: CompiledGodotGameplay) -> None:
    if set(artifact.files) != CORE_PATHS:
        raise PermissionError("Godot gameplay artifact exceeds its declared output surface")
    if artifact.asset.path != ASSET_PATH or artifact.asset.media_type != "image/png":
        raise PermissionError("Godot gameplay artifact contains an unapproved binary asset")
    if hashlib.sha256(artifact.asset.bytes()).hexdigest() != artifact.asset.sha256:
        raise PermissionError("Godot gameplay visual asset digest changed after approval")
    plan_sha = _canonical_sha256({
        "gameplay": artifact.gameplay.model_dump(mode="json"),
        "concept": artifact.concept.model_dump(mode="json"),
        "asset_sha256": artifact.asset.sha256,
    })
    if artifact.plan_sha256 != plan_sha:
        raise PermissionError("Godot gameplay plan digest changed after compilation")
    expected_bundle = _canonical_sha256({
        "plan_sha256": plan_sha,
        "files": artifact.files,
        "asset_sha256": artifact.asset.sha256,
    })
    if artifact.bundle_sha256 != expected_bundle:
        raise PermissionError("Godot gameplay bundle digest changed after compilation")
    total = sum(len(item.encode("utf-8")) for item in artifact.files.values()) + len(artifact.asset.bytes())
    if len(artifact.files) + 1 > GODOT_GAMEPLAY_MANIFEST.output.max_file_count:
        raise PermissionError("Godot gameplay artifact exceeds its file-count limit")
    if total > GODOT_GAMEPLAY_MANIFEST.output.max_total_bytes:
        raise PermissionError("Godot gameplay artifact exceeds its byte limit")


def _validate_materialized(artifact: CompiledGodotGameplay, root: Path) -> None:
    destination = root.resolve()
    for raw_path, expected in artifact.files.items():
        target = (destination / Path(*PurePosixPath(raw_path).parts)).resolve()
        if not target.is_relative_to(destination) or not target.is_file():
            raise PermissionError(f"materialized Godot gameplay file is missing: {raw_path}")
        if target.read_text(encoding="utf-8") != expected:
            raise PermissionError(f"materialized Godot gameplay file changed after approval: {raw_path}")
    asset = (destination / Path(*PurePosixPath(artifact.asset.path).parts)).resolve()
    if not asset.is_file() or _file_sha256(asset) != artifact.asset.sha256:
        raise PermissionError("materialized Godot gameplay visual asset changed after approval")


class GodotGameplayExecutionAdapter:
    adapter_id = "godot.gameplay.execution.v1"

    def materialize(self, artifact: CompiledGodotGameplay, root: Path) -> None:
        _validate_artifact(artifact)
        destination = root.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        staging = destination / f".khalinos-godot-gameplay-{uuid4().hex}"
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
                    raise PermissionError("Godot gameplay artifact contains an unsafe output path")
                if target.exists() and target.read_bytes() != payload:
                    raise FileExistsError(f"Godot Gameplay ToolPack refuses to overwrite {raw_path}")
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


class GodotGameplayEvidenceAdapter:
    adapter_id = "godot.gameplay.evidence.v1"

    def verify(
        self,
        artifact: CompiledGodotGameplay,
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
        receipt_path = evidence_dir / "godot-gameplay-probe.json"
        probe = subprocess.run(
            [str(executable), "--language", "en", "--headless", "--path", str(root.resolve()),
             "--script", "res://scripts/khalinos_gameplay_probe.gd", "--", f"--output={receipt_path.resolve()}"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        xvfb, environment = _start_xvfb(artifact.gameplay.viewport_width, artifact.gameplay.viewport_height)
        try:
            prefix = evidence_dir / "godot-gameplay-render.png"
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
        frames = sorted(evidence_dir.glob("godot-gameplay-render????????.png"))
        capture = frames[-1] if frames else prefix
        dimensions = png_dimensions(capture.read_bytes()) if capture.is_file() else (0, 0)
        checks = {
            "approved_executable_digest": True,
            "asset_import_process": imported.returncode == 0,
            "headless_process": probe.returncode == 0,
            "probe_schema": receipt.get("schema_version") == "khalinos-godot-gameplay-probe-v1",
            "formation_instantiated": receipt.get("formation_count") == len(artifact.gameplay.heroes),
            "movement_applied": receipt.get("movement_applied") is True,
            "enemy_spawned": receipt.get("enemy_spawned") is True,
            "auto_ability_applied": receipt.get("auto_ability_applied") is True,
            "shared_health_initialized": receipt.get("shared_health_initialized") is True,
            "level_choice_offered": receipt.get("level_choice_offered") is True,
            "level_choice_applied": receipt.get("level_choice_applied") is True,
            "deterministic_seed_bound": receipt.get("seed") == artifact.gameplay.deterministic_seed,
            "probe_passed": receipt.get("passed") is True,
            "trusted_asset_materialized": _file_sha256(root / ASSET_PATH) == artifact.asset.sha256,
            "display_render_process": rendered.returncode == 0,
            "display_render_frames": len(frames) == 3,
            "display_render_dimensions": dimensions == (artifact.gameplay.viewport_width, artifact.gameplay.viewport_height),
            "display_render_nontrivial": capture.is_file() and capture.stat().st_size > 5_000,
        }
        issues = [name for name, passed in checks.items() if not passed]
        observation = (
            f"Godot deterministic gameplay probe exercised formation movement, enemy spawning, automatic abilities, "
            f"shared health, and level choice with seed={artifact.gameplay.deterministic_seed}; "
            f"the display runtime produced {len(frames)} {dimensions[0]}x{dimensions[1]} PNG frames."
        )
        return DeterministicEvidence(
            passed=not issues,
            checks=checks,
            issues=issues,
            screenshot_names=[capture.name] if capture.is_file() else [],
            criterion_evidence={criterion: [observation] for criterion in acceptance_criteria},
        )


GODOT_GAMEPLAY_IMPLEMENTATION_SOURCES = (
    "agents.py", "godot_gameplay.py", "godot_gameplay_toolpack.py",
    "godot_gameplay_workflow.py", "run_router.py", "visual_assets.py",
)

GODOT_GAMEPLAY_MANIFEST = ToolPackManifest(
    toolpack_id="godot.gameplay",
    version="1.0.0",
    display_name="Godot Gameplay Vertical Slice ToolPack",
    description="Compiles bounded data-driven 2D gameplay plans with Nano Banana visual foundations and proves real mechanics in Godot runtime and rendered evidence.",
    implementation_sha256=source_set_sha256(Path(__file__).parent, GODOT_GAMEPLAY_IMPLEMENTATION_SOURCES),
    execution_adapter_id=GodotGameplayExecutionAdapter.adapter_id,
    project_kinds=("godot",),
    work_modes=("new_product_build",),
    capabilities=(
        CapabilityDeclaration(capability_id="godot.gameplay.asset", operations=("generate", "observe"), scopes=("artifact:write", "model:image")),
        CapabilityDeclaration(capability_id="godot.gameplay.control", operations=("build",), scopes=("artifact:write", "godot:scene", "godot:script")),
        CapabilityDeclaration(capability_id="godot.gameplay.evidence", operations=("execute", "observe"), scopes=("runtime:display", "runtime:headless")),
    ),
    routing=RoutingContract(
        primary_project_kind="godot",
        supported_outcomes=(
            "Nano Banana visual foundation validated in a real Godot render",
            "bounded playable Godot 2D top-down action vertical slices",
            "data-driven survival loops with movement enemies automatic abilities shared health and level choices",
        ),
        excluded_outcomes=(
            "3D multiplayer networking arbitrary plugins or arbitrary user-authored scripts",
            "finished production games unrestricted mechanics or repair of existing Godot projects",
            "platform exports distribution storefront integration or backend services",
        ),
        selection_guidance="Choose this route for a bounded playable 2D top-down Godot vertical slice whose mechanics fit the declared data-driven survival and action primitives.",
    ),
    output=OutputContract(
        artifact_kind="godot.gameplay-vertical-slice",
        authorized_paths=("KHALINOS_GAMEPLAY.json", "README.md", "assets/visual-foundation.png", "project.godot", "scenes/gameplay.tscn", "scripts/khalinos_gameplay.gd", "scripts/khalinos_gameplay_probe.gd"),
        max_file_count=12,
        max_total_bytes=3_000_000,
    ),
    evidence=EvidenceContract(
        adapter_id=GodotGameplayEvidenceAdapter.adapter_id,
        evidence_types=("godot.display.render", "godot.gameplay.probe", "runtime.assertion", "runtime.screenshot", "visual.asset.loaded"),
        network_isolated=False,
        independent_verifier_required=True,
    ),
)

GODOT_GAMEPLAY_TOOLPACK = RegisteredToolPack[CompiledGodotGameplay, DeterministicEvidence](
    manifest=GODOT_GAMEPLAY_MANIFEST,
    execution_adapter=GodotGameplayExecutionAdapter(),
    evidence_adapter=GodotGameplayEvidenceAdapter(),
)
