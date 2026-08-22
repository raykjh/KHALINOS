"""Deterministic atlas composition for KHALINOS-generated combat VFX."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict

from khalinos.models import ArtifactAsset


EFFECT_ATLAS_PATH = "assets/combat-vfx-atlas.png"
EFFECT_SELECTION_PATH = "KHALINOS_EFFECT_SELECTION.json"
EFFECT_ATLAS_MANIFEST_PATH = "KHALINOS_EFFECT_ATLAS.json"
EFFECT_RECEIPT_PATH = "KHALINOS_EFFECT_RECEIPT.json"
EFFECT_FRAME_SIZE = 192
EFFECT_FRAMES = 9
EFFECT_COLUMNS = 9
ProfileId = Literal["godot.trinity-top-down", "godot.side-scroll-destination"]

_SOURCE_ROOT = Path(__file__).with_name("assets") / "vfx"
_SOURCES = {
    "warrior_slash": (
        "vfx-warrior-golden-slash-3x3.png",
        "898768eeec2a19459ccf75f1d024da29a8c928f29a15287988e41191d309aa88",
    ),
    "archer_impact": (
        "vfx-archer-arrow-impact-3x3.png",
        "09551b0e8fca79485180737a05c1982a8942c0a2e080fc4c88c18b5281e1e326",
    ),
    "healer_restoration": (
        "vfx-healer-restoration-pulse-3x3.png",
        "24442b755c5a9003a8ba35e4a9ced72189111408a9fee94482a86cae684fdd22",
    ),
    "enemy_claw": (
        "vfx-enemy-claw-poison-hit-3x3.png",
        "8714571f851a0be8f8365d4c1c342bcbdd4e9194578827df10305f59b600a1e9",
    ),
}


class EffectBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-effect-bundle-v1"] = "khalinos-effect-bundle-v1"
    profile_id: ProfileId
    atlas: ArtifactAsset
    selection_manifest: dict[str, object]
    atlas_manifest: dict[str, object]
    receipt: dict[str, object]

    def text_files(self) -> dict[str, str]:
        return {
            EFFECT_SELECTION_PATH: json.dumps(
                self.selection_manifest, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
            EFFECT_ATLAS_MANIFEST_PATH: json.dumps(
                self.atlas_manifest, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
            EFFECT_RECEIPT_PATH: json.dumps(
                self.receipt, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
        }


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_effect_bundle(profile_id: ProfileId) -> EffectBundle:
    """Execute Effect Selector -> Effect Atlas -> Effect Receipt."""

    roles = tuple(_SOURCES)
    atlas = Image.new(
        "RGBA",
        (EFFECT_COLUMNS * EFFECT_FRAME_SIZE, len(roles) * EFFECT_FRAME_SIZE),
        (0, 0, 0, 0),
    )
    selected: list[dict[str, object]] = []
    slots: list[dict[str, object]] = []
    for row, role in enumerate(roles):
        filename, expected_sha = _SOURCES[role]
        source_path = _SOURCE_ROOT / filename
        payload = source_path.read_bytes()
        if _sha256(payload) != expected_sha:
            raise PermissionError(f"generated VFX source changed: {filename}")
        with Image.open(io.BytesIO(payload)) as opened:
            source = opened.convert("RGBA")
        if source.size != (1254, 1254):
            raise PermissionError(f"generated VFX source dimensions changed: {filename}")
        source_cell = source.width // 3
        for frame in range(EFFECT_FRAMES):
            source_x = frame % 3
            source_y = frame // 3
            cell = source.crop((
                source_x * source_cell,
                source_y * source_cell,
                (source_x + 1) * source_cell,
                (source_y + 1) * source_cell,
            ))
            if cell.getchannel("A").getbbox() is None:
                raise PermissionError(f"generated VFX frame is empty: {role}:{frame}")
            normalized = cell.resize(
                (EFFECT_FRAME_SIZE, EFFECT_FRAME_SIZE), Image.Resampling.NEAREST
            )
            atlas.alpha_composite(normalized, (frame * EFFECT_FRAME_SIZE, row * EFFECT_FRAME_SIZE))
        selected.append({
            "role": role,
            "source_filename": filename,
            "source_sha256": expected_sha,
            "frames": EFFECT_FRAMES,
            "source_grid": [3, 3],
            "alpha_required": True,
        })
        slots.append({
            "role": role,
            "row": row,
            "frames": EFFECT_FRAMES,
            "frame_size": EFFECT_FRAME_SIZE,
        })

    output = io.BytesIO()
    atlas.save(output, format="PNG", optimize=False)
    atlas_payload = output.getvalue()
    artifact = ArtifactAsset(
        path=EFFECT_ATLAS_PATH,
        data_base64=base64.b64encode(atlas_payload).decode("ascii"),
        sha256=_sha256(atlas_payload),
        width=atlas.width,
        height=atlas.height,
    )
    selection = {
        "schema_version": "khalinos-effect-selection-v1",
        "profile_id": profile_id,
        "selector": "fixed-shared-combat-feedback-v1",
        "effects": selected,
    }
    atlas_manifest = {
        "schema_version": "khalinos-effect-atlas-v1",
        "profile_id": profile_id,
        "atlas_path": EFFECT_ATLAS_PATH,
        "atlas_sha256": artifact.sha256,
        "frame_size": EFFECT_FRAME_SIZE,
        "columns": EFFECT_COLUMNS,
        "slots": slots,
    }
    receipt = {
        "schema_version": "khalinos-effect-receipt-v1",
        "profile_id": profile_id,
        "provider": "OpenAI built-in ImageGen",
        "created_for_project": "KHALINOS",
        "created_on": "2026-08-22",
        "external_stock_asset_license_required": False,
        "copyright_status_adjudicated": False,
        "source_effects": selected,
        "selection_sha256": _canonical_sha256(selection),
        "output_atlas_path": EFFECT_ATLAS_PATH,
        "output_atlas_sha256": artifact.sha256,
        "frame_contract": {"frames_per_effect": EFFECT_FRAMES, "playback": "forward_once"},
        "passed": True,
    }
    return EffectBundle(
        profile_id=profile_id,
        atlas=artifact,
        selection_manifest=selection,
        atlas_manifest=atlas_manifest,
        receipt=receipt,
    )
