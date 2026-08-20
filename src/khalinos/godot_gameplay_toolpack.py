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
from khalinos.sprite_assets import (
    SPRITE_ATLAS_MANIFEST_PATH,
    SPRITE_ATLAS_PATH,
    SPRITE_SEGMENTATION_CONTRACT,
)
from khalinos.toolpacks import (
    CapabilityDeclaration,
    EvidenceContract,
    ExternalDependency,
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
SPRITE_PATHS = {SPRITE_ATLAS_MANIFEST_PATH}


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
    expected_paths = CORE_PATHS | (SPRITE_PATHS if artifact.sprite_atlas is not None else set())
    if set(artifact.files) != expected_paths:
        raise PermissionError("Godot gameplay artifact exceeds its declared output surface")
    if artifact.asset.path != ASSET_PATH or artifact.asset.media_type != "image/png":
        raise PermissionError("Godot gameplay artifact contains an unapproved binary asset")
    if hashlib.sha256(artifact.asset.bytes()).hexdigest() != artifact.asset.sha256:
        raise PermissionError("Godot gameplay visual asset digest changed after approval")
    if (artifact.sprite_plan is None) != (artifact.sprite_atlas is None):
        raise PermissionError("Godot gameplay sprite plan and atlas are not atomic")
    if artifact.sprite_contract_required and artifact.sprite_atlas is None:
        raise PermissionError("final Godot gameplay artifact is missing its required sprite atlas")
    if artifact.sprite_atlas is not None:
        if artifact.sprite_segmentation_contract_sha256 != SPRITE_SEGMENTATION_CONTRACT.sha256():
            raise PermissionError("Godot gameplay sprite segmentation contract changed after approval")
        if artifact.sprite_atlas.path != SPRITE_ATLAS_PATH or artifact.sprite_atlas.media_type != "image/png":
            raise PermissionError("Godot gameplay artifact contains an unapproved sprite atlas")
        if hashlib.sha256(artifact.sprite_atlas.bytes()).hexdigest() != artifact.sprite_atlas.sha256:
            raise PermissionError("Godot gameplay sprite atlas digest changed after approval")
        expected_manifest = json.dumps(artifact.sprite_plan.manifest(), ensure_ascii=False, indent=2) + "\n"
        if artifact.files.get(SPRITE_ATLAS_MANIFEST_PATH) != expected_manifest:
            raise PermissionError("Godot gameplay sprite manifest changed after approval")
    plan_sha = _canonical_sha256({
        "gameplay": artifact.gameplay.model_dump(mode="json"),
        "concept": artifact.concept.model_dump(mode="json"),
        "asset_sha256": artifact.asset.sha256,
        "sprite_plan": artifact.sprite_plan.model_dump(mode="json") if artifact.sprite_plan else None,
        "sprite_atlas_sha256": artifact.sprite_atlas.sha256 if artifact.sprite_atlas else None,
        "sprite_contract_required": artifact.sprite_contract_required,
        "sprite_segmentation_contract_sha256": artifact.sprite_segmentation_contract_sha256,
    })
    if artifact.plan_sha256 != plan_sha:
        raise PermissionError("Godot gameplay plan digest changed after compilation")
    expected_bundle = _canonical_sha256({
        "plan_sha256": plan_sha,
        "files": artifact.files,
        "asset_sha256": artifact.asset.sha256,
        "sprite_atlas_sha256": artifact.sprite_atlas.sha256 if artifact.sprite_atlas else None,
        "sprite_contract_required": artifact.sprite_contract_required,
        "sprite_segmentation_contract_sha256": artifact.sprite_segmentation_contract_sha256,
    })
    if artifact.bundle_sha256 != expected_bundle:
        raise PermissionError("Godot gameplay bundle digest changed after compilation")
    binaries = [artifact.asset, *([artifact.sprite_atlas] if artifact.sprite_atlas else [])]
    total = sum(len(item.encode("utf-8")) for item in artifact.files.values()) + sum(len(item.bytes()) for item in binaries)
    if len(artifact.files) + len(binaries) > GODOT_GAMEPLAY_MANIFEST.output.max_file_count:
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
    if artifact.sprite_atlas is not None:
        sprite = (destination / SPRITE_ATLAS_PATH).resolve()
        if not sprite.is_file() or _file_sha256(sprite) != artifact.sprite_atlas.sha256:
            raise PermissionError("materialized Godot gameplay sprite atlas changed after approval")


class GodotGameplayExecutionAdapter:
    adapter_id = "godot.gameplay.execution.v2"

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
        if artifact.sprite_atlas is not None:
            payloads[artifact.sprite_atlas.path] = artifact.sprite_atlas.bytes()
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
    adapter_id = "godot.gameplay.evidence.v2"

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
        import_log = evidence_dir / "godot-gameplay-import.log"
        imported = subprocess.run(
            [str(executable), "--language", "en", "--headless", "--log-file", str(import_log.resolve()),
             "--path", str(root.resolve()), "--editor", "--quit"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        receipt_path = evidence_dir / "godot-gameplay-probe.json"
        probe_log = evidence_dir / "godot-gameplay-probe.log"
        probe = subprocess.run(
            [str(executable), "--language", "en", "--headless", "--log-file", str(probe_log.resolve()),
             "--path", str(root.resolve()),
             "--script", "res://scripts/khalinos_gameplay_probe.gd", "--", f"--output={receipt_path.resolve()}"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, shell=False, check=False,
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        xvfb, environment = _start_xvfb(artifact.gameplay.viewport_width, artifact.gameplay.viewport_height)
        try:
            prefix = evidence_dir / "godot-gameplay-render.png"
            render_log = evidence_dir / "godot-gameplay-render.log"
            rendered = subprocess.run(
                [str(executable), "--language", "en", "--windowed", "--log-file", str(render_log.resolve()),
                 "--path", str(root.resolve()),
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
        expected_stats = {
            "health": float(sum(item.health for item in artifact.gameplay.heroes)),
            "attack": float(sum(item.attack for item in artifact.gameplay.heroes)),
            "defense": float(sum(item.defense for item in artifact.gameplay.heroes)),
            "attack_speed": float(sum(item.attack_speed for item in artifact.gameplay.heroes)),
            "move_speed": float(sum(item.move_speed for item in artifact.gameplay.heroes)),
        }
        observed_stats = receipt.get("party_stats", {})
        checks = {
            "approved_executable_digest": True,
            "asset_import_process": imported.returncode == 0,
            "headless_process": probe.returncode == 0,
            "probe_schema": receipt.get("schema_version") == "khalinos-godot-gameplay-probe-v3",
            "formation_instantiated": receipt.get("formation_count") == len(artifact.gameplay.heroes),
            "movement_applied": receipt.get("movement_applied") is True,
            "enemy_spawned": receipt.get("enemy_spawned") is True,
            "auto_ability_applied": receipt.get("auto_ability_applied") is True,
            "shared_health_initialized": receipt.get("shared_health_initialized") is True,
            "level_choice_offered": receipt.get("level_choice_offered") is True,
            "level_choice_applied": receipt.get("level_choice_applied") is True,
            "session_duration_bound": receipt.get("session_seconds") == artifact.gameplay.session_seconds,
            "level_schedule_bound": (
                receipt.get("level_count") == artifact.gameplay.level_count
                and receipt.get("level_interval_seconds") == artifact.gameplay.level_interval_seconds
            ),
            "upgrade_role_order_executed": receipt.get("upgrade_role_order_valid") is True,
            "three_choice_profession_contract": receipt.get("upgrade_choice_contract_valid") is True,
            "seeded_profession_alternatives": (
                receipt.get("profession_choice_mode") == "seeded_random_alternatives"
                and receipt.get("seeded_alternatives_valid") is True
                and receipt.get("same_seed_repeatable") is True
                and receipt.get("different_seed_variation_when_possible") is True
            ),
            "party_stats_aggregated": (
                receipt.get("team_stat_mode") == "sum"
                and all(abs(float(observed_stats.get(key, -1)) - value) < 0.001 for key, value in expected_stats.items())
            ),
            "resurrection_contract_executed": (
                receipt.get("resurrection_stored") is True
                and receipt.get("resurrection_consumed") is True
            ),
            "victory_at_session_end": receipt.get("victory_at_session_end") is True,
            "deterministic_seed_bound": receipt.get("seed") == artifact.gameplay.deterministic_seed,
            "probe_passed": receipt.get("passed") is True,
            "trusted_asset_materialized": _file_sha256(root / ASSET_PATH) == artifact.asset.sha256,
            "sprite_contract_present": not artifact.sprite_contract_required or artifact.sprite_atlas is not None,
            "sprite_atlas_loaded": not artifact.sprite_contract_required or receipt.get("sprite_atlas_loaded") is True,
            "sprite_slot_count_bound": (
                not artifact.sprite_contract_required
                or (artifact.sprite_plan is not None and receipt.get("sprite_slot_count") == len(artifact.sprite_plan.slots))
            ),
            "all_sprite_ids_mapped": not artifact.sprite_contract_required or receipt.get("all_sprite_ids_mapped") is True,
            "trusted_sprite_atlas_materialized": (
                not artifact.sprite_contract_required
                or (artifact.sprite_atlas is not None and _file_sha256(root / SPRITE_ATLAS_PATH) == artifact.sprite_atlas.sha256)
            ),
            "display_render_process": rendered.returncode == 0,
            "display_render_frames": len(frames) == 3,
            "display_render_dimensions": dimensions == (artifact.gameplay.viewport_width, artifact.gameplay.viewport_height),
            "display_render_nontrivial": capture.is_file() and capture.stat().st_size > 5_000,
        }
        issues = [name for name, passed in checks.items() if not passed]
        observation = (
            f"Godot deterministic gameplay probe exercised formation movement, enemy spawning, automatic abilities, "
            f"summed party stats, {artifact.gameplay.session_seconds}-second victory, "
            f"{artifact.gameplay.level_count}-level progression every {artifact.gameplay.level_interval_seconds} seconds, "
            f"ordered three-option profession choices with one guaranteed rank-up and two distinct seeded alternatives, "
            f"and bounded resurrection with seed={artifact.gameplay.deterministic_seed}; "
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
    "godot_gameplay_workflow.py", "run_router.py", "sprite_assets.py", "visual_assets.py",
)

GODOT_GAMEPLAY_MANIFEST = ToolPackManifest(
    toolpack_id="godot.gameplay",
    version="1.4.0",
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
        CapabilityDeclaration(capability_id="godot.sprite.asset", operations=("generate", "normalize", "observe"), scopes=("artifact:write", "model:image")),
    ),
    external_dependencies=(
        ExternalDependency(
            dependency_id="isnet-anime.onnx",
            kind="model",
            version=SPRITE_SEGMENTATION_CONTRACT.model_version,
            sha256=SPRITE_SEGMENTATION_CONTRACT.model_sha256,
            byte_size=SPRITE_SEGMENTATION_CONTRACT.model_bytes,
            source_url=SPRITE_SEGMENTATION_CONTRACT.model_url,
            license_id=SPRITE_SEGMENTATION_CONTRACT.license_id,
        ),
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
        authorized_paths=("KHALINOS_GAMEPLAY.json", "KHALINOS_SPRITE_ATLAS.json", "README.md", "assets/sprite-atlas.png", "assets/visual-foundation.png", "project.godot", "scenes/gameplay.tscn", "scripts/khalinos_gameplay.gd", "scripts/khalinos_gameplay_probe.gd"),
        max_file_count=12,
        max_total_bytes=5_500_000,
    ),
    evidence=EvidenceContract(
        adapter_id=GodotGameplayEvidenceAdapter.adapter_id,
        evidence_types=("godot.display.render", "godot.gameplay.probe", "runtime.assertion", "runtime.screenshot", "seeded.profession.choice", "sprite.atlas.loaded", "sprite.segmentation.digest", "sprite.visual.completeness", "visual.asset.loaded"),
        network_isolated=False,
        independent_verifier_required=True,
    ),
)

GODOT_GAMEPLAY_TOOLPACK = RegisteredToolPack[CompiledGodotGameplay, DeterministicEvidence](
    manifest=GODOT_GAMEPLAY_MANIFEST,
    execution_adapter=GodotGameplayExecutionAdapter(),
    evidence_adapter=GodotGameplayEvidenceAdapter(),
)
