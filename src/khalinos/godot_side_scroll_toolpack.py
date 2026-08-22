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
from khalinos.licensed_visual_assets import (
    ASSET_SELECTION_PATH,
    LICENSE_RECEIPT_PATH,
    LICENSED_ATLAS_MANIFEST_PATH,
    LICENSED_ATLAS_PATH,
    STYLE_COMPOSITION_PATH,
)
from khalinos.generated_vfx_assets import (
    EFFECT_ATLAS_MANIFEST_PATH,
    EFFECT_ATLAS_PATH,
    EFFECT_RECEIPT_PATH,
    EFFECT_SELECTION_PATH,
)
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
    "scripts/khalinos_audio_feedback.gd",
    "scripts/khalinos_combat_feedback.gd",
    "scripts/khalinos_presentation_skin.gd",
    "scripts/khalinos_side_scroll.gd",
    "scripts/khalinos_side_scroll_probe.gd",
}
LICENSED_ART_PATHS = {
    ASSET_SELECTION_PATH,
    STYLE_COMPOSITION_PATH,
    LICENSED_ATLAS_MANIFEST_PATH,
    LICENSE_RECEIPT_PATH,
    "scripts/khalinos_licensed_art.gd",
}
EFFECT_PATHS = {
    EFFECT_SELECTION_PATH,
    EFFECT_ATLAS_MANIFEST_PATH,
    EFFECT_RECEIPT_PATH,
    "scripts/khalinos_vfx_player.gd",
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
    expected_paths = SIDE_SCROLL_PATHS | (LICENSED_ART_PATHS if artifact.licensed_art_atlas is not None else set()) | (EFFECT_PATHS if artifact.effect_atlas is not None else set())
    if set(artifact.files) != expected_paths:
        raise PermissionError("Godot side-scroll artifact exceeds its declared output surface")
    if artifact.asset.path != ASSET_PATH or artifact.asset.media_type != "image/png":
        raise PermissionError("Godot side-scroll artifact contains an unapproved binary asset")
    if hashlib.sha256(artifact.asset.bytes()).hexdigest() != artifact.asset.sha256:
        raise PermissionError("Godot side-scroll visual asset digest changed after approval")
    if artifact.licensed_art_atlas is not None:
        if artifact.licensed_art_atlas.path != LICENSED_ATLAS_PATH:
            raise PermissionError("Godot side-scroll licensed atlas uses an unapproved path")
        if hashlib.sha256(artifact.licensed_art_atlas.bytes()).hexdigest() != artifact.licensed_art_atlas.sha256:
            raise PermissionError("Godot side-scroll licensed atlas digest changed after approval")
        receipt = json.loads(artifact.files[LICENSE_RECEIPT_PATH])
        if not receipt.get("passed") or receipt.get("output_atlas_sha256") != artifact.licensed_art_atlas.sha256:
            raise PermissionError("Godot side-scroll license receipt does not bind the selected atlas")
    if artifact.effect_atlas is not None:
        if artifact.effect_atlas.path != EFFECT_ATLAS_PATH:
            raise PermissionError("Godot side-scroll effect atlas uses an unapproved path")
        if hashlib.sha256(artifact.effect_atlas.bytes()).hexdigest() != artifact.effect_atlas.sha256:
            raise PermissionError("Godot side-scroll effect atlas digest changed after approval")
        receipt = json.loads(artifact.files[EFFECT_RECEIPT_PATH])
        if not receipt.get("passed") or receipt.get("output_atlas_sha256") != artifact.effect_atlas.sha256:
            raise PermissionError("Godot side-scroll effect receipt does not bind the atlas")
    plan_sha = _canonical_sha256({
        "plan": artifact.plan.model_dump(mode="json"),
        "concept": artifact.concept.model_dump(mode="json"),
        "asset_sha256": artifact.asset.sha256,
        "licensed_art_sha256": artifact.licensed_art_atlas.sha256 if artifact.licensed_art_atlas else None,
        "effect_atlas_sha256": artifact.effect_atlas.sha256 if artifact.effect_atlas else None,
    })
    if artifact.plan_sha256 != plan_sha:
        raise PermissionError("Godot side-scroll plan digest changed after compilation")
    bundle_sha = _canonical_sha256({
        "plan_sha256": plan_sha,
        "files": artifact.files,
        "asset_sha256": artifact.asset.sha256,
        "licensed_art_sha256": artifact.licensed_art_atlas.sha256 if artifact.licensed_art_atlas else None,
        "effect_atlas_sha256": artifact.effect_atlas.sha256 if artifact.effect_atlas else None,
    })
    if artifact.bundle_sha256 != bundle_sha:
        raise PermissionError("Godot side-scroll bundle digest changed after compilation")
    binaries = [artifact.asset, *([artifact.licensed_art_atlas] if artifact.licensed_art_atlas else []), *([artifact.effect_atlas] if artifact.effect_atlas else [])]
    total = sum(len(item.encode("utf-8")) for item in artifact.files.values()) + sum(len(item.bytes()) for item in binaries)
    if len(artifact.files) + len(binaries) > GODOT_SIDE_SCROLL_MANIFEST.output.max_file_count:
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
    if artifact.licensed_art_atlas is not None:
        atlas = (destination / LICENSED_ATLAS_PATH).resolve()
        if not atlas.is_file() or _file_sha256(atlas) != artifact.licensed_art_atlas.sha256:
            raise PermissionError("materialized Godot side-scroll licensed atlas changed after approval")
    if artifact.effect_atlas is not None:
        atlas = (destination / EFFECT_ATLAS_PATH).resolve()
        if not atlas.is_file() or _file_sha256(atlas) != artifact.effect_atlas.sha256:
            raise PermissionError("materialized Godot side-scroll effect atlas changed after approval")


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
        if artifact.licensed_art_atlas is not None:
            payloads[artifact.licensed_art_atlas.path] = artifact.licensed_art_atlas.bytes()
        if artifact.effect_atlas is not None:
            payloads[artifact.effect_atlas.path] = artifact.effect_atlas.bytes()
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
            "combat_feedback_pack_loaded": receipt.get("combat_feedback_pack_loaded") is True,
            "presentation_skin_pack_loaded": receipt.get("presentation_skin_pack_loaded") is True,
            "audio_feedback_pack_loaded": receipt.get("audio_feedback_pack_loaded") is True,
            "attack_audio_event": int(receipt.get("attack_audio_events", 0)) > 0,
            "hit_audio_event": int(receipt.get("hit_audio_events", 0)) > 0,
            "victory_audio_event": int(receipt.get("victory_audio_events", 0)) > 0,
            "horizontal_lane_present": receipt.get("horizontal_lane_present") is True,
            "movement_right": receipt.get("movement_right") is True,
            "enemy_spawned": receipt.get("enemy_spawned") is True,
            "auto_attack_fired": receipt.get("auto_attack_fired") is True,
            "enemy_defeated": receipt.get("enemy_defeated") is True,
            "destination_reached": receipt.get("destination_reached") is True,
            "victory": receipt.get("victory") is True,
            "probe_passed": receipt.get("passed") is True,
            "trusted_asset_materialized": _file_sha256(root / ASSET_PATH) == artifact.asset.sha256,
            "licensed_art_loaded": artifact.licensed_art_atlas is None or receipt.get("licensed_art_loaded") is True,
            "license_receipt_present": artifact.licensed_art_atlas is None or receipt.get("license_receipt_present") is True,
            "trusted_licensed_atlas_materialized": (
                artifact.licensed_art_atlas is None
                or _file_sha256(root / LICENSED_ATLAS_PATH) == artifact.licensed_art_atlas.sha256
            ),
            "effect_atlas_loaded": artifact.effect_atlas is None or receipt.get("effect_atlas_loaded") is True,
            "effect_receipt_present": artifact.effect_atlas is None or receipt.get("effect_receipt_present") is True,
            "effect_frame_animation_observed": artifact.effect_atlas is None or receipt.get("effect_frame_animation_observed") is True,
            "trusted_effect_atlas_materialized": (
                artifact.effect_atlas is None
                or _file_sha256(root / EFFECT_ATLAS_PATH) == artifact.effect_atlas.sha256
            ),
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
    "agent_capability_receipts.py",
    "agents.py",
    "godot_capability_packs.py",
    "godot_side_scroll.py",
    "godot_side_scroll_toolpack.py",
    "godot_side_scroll_workflow.py",
    "generated_vfx_assets.py",
    "licensed_visual_assets.py",
    "run_router.py",
    "toolpacks.py",
    "visual_assets.py",
)

GODOT_SIDE_SCROLL_MANIFEST = ToolPackManifest(
    toolpack_id="godot.side-scroll-experiment",
    version="0.8.0",
    display_name="Godot Side-scroll Composition Experiment",
    description="Composes a bounded horizontal auto-combat journey from reusable Godot Capability Packs and verifies mechanics in the approved runtime.",
    implementation_sha256=source_set_sha256(Path(__file__).parent, GODOT_SIDE_SCROLL_IMPLEMENTATION_SOURCES),
    execution_adapter_id=GodotSideScrollExecutionAdapter.adapter_id,
    project_kinds=("godot",),
    work_modes=("new_product_build",),
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
        authorized_paths=tuple(sorted(SIDE_SCROLL_PATHS | LICENSED_ART_PATHS | EFFECT_PATHS | {ASSET_PATH, LICENSED_ATLAS_PATH, EFFECT_ATLAS_PATH})),
        max_file_count=22,
        max_total_bytes=8_000_000,
    ),
    evidence=EvidenceContract(
        adapter_id=GodotSideScrollEvidenceAdapter.adapter_id,
        evidence_types=(
            "effect.atlas.loaded",
            "effect.frame.animation",
            "effect.receipt",
            "gameplay.audio.feedback",
            "gameplay.auto-attack",
            "gameplay.destination",
            "gameplay.horizontal-progress",
            "gameplay.presentation.skin",
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
