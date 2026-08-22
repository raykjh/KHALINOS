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
EFFECT_FRAME_SIZE = 112
EFFECT_FRAMES = 9
EFFECT_CANDIDATES_PER_ROW = 2
EFFECT_COLUMNS = EFFECT_FRAMES * EFFECT_CANDIDATES_PER_ROW
ProfileId = Literal["godot.trinity-top-down", "godot.side-scroll-destination"]

_SOURCE_ROOT = Path(__file__).with_name("assets") / "vfx"
_SOURCES = {
    "warrior_golden_slash": (
        "warrior",
        "vfx-warrior-golden-slash-3x3.png",
        "898768eeec2a19459ccf75f1d024da29a8c928f29a15287988e41191d309aa88",
    ),
    "warrior_cyan_whirlwind": (
        "warrior",
        "vfx-warrior-cyan-whirlwind-3x3.png",
        "c8f02bd4af7a6644cbd7e55ef0d008f611e575b0bb49e1fe078cb3c61278459f",
    ),
    "warrior_crimson_heavy": (
        "warrior",
        "vfx-warrior-crimson-heavy-strike-3x3.png",
        "aa296151f154efdb65fa2dfcd2078b14e44e5ec413feb784bc5bce2c0a1b04fc",
    ),
    "archer_arrow_impact": (
        "archer",
        "vfx-archer-arrow-impact-3x3.png",
        "09551b0e8fca79485180737a05c1982a8942c0a2e080fc4c88c18b5281e1e326",
    ),
    "archer_emerald_volley": (
        "archer",
        "vfx-archer-emerald-volley-3x3.png",
        "d180648f1edce3c54128b17a7c437af205c816df16920395a7bce45d09373adb",
    ),
    "archer_violet_rain": (
        "archer",
        "vfx-archer-violet-rain-3x3.png",
        "02b16afe96c30872a09326e082bd4950f829a705ea344e207ef5f50f29f1a891",
    ),
    "healer_restoration_pulse": (
        "healer",
        "vfx-healer-restoration-pulse-3x3.png",
        "24442b755c5a9003a8ba35e4a9ced72189111408a9fee94482a86cae684fdd22",
    ),
    "healer_golden_shield": (
        "healer",
        "vfx-healer-golden-shield-3x3.png",
        "998c6b6095fd54b4bc0d315611544daa68994fd705e2a23cf5c25a7ac8d6745a",
    ),
    "healer_blue_resurrection": (
        "healer",
        "vfx-healer-blue-resurrection-3x3.png",
        "dd7de25683200aca522564b6ada4b50dced2f008d531bac37b47c30917feafc5",
    ),
    "enemy_claw_poison": (
        "enemy",
        "vfx-enemy-claw-poison-hit-3x3.png",
        "8714571f851a0be8f8365d4c1c342bcbdd4e9194578827df10305f59b600a1e9",
    ),
    "enemy_red_bite": (
        "enemy",
        "vfx-enemy-red-bite-3x3.png",
        "7025a87626e93c649f2613f39b21ef78facfae9f67d77aa4c093741dfb7d8545",
    ),
    "enemy_purple_curse": (
        "enemy",
        "vfx-enemy-purple-curse-3x3.png",
        "768b1088aed5a24d5318e1e0d4ddf4d480ab502f378801763152729468024e1d",
    ),
}

_PROFILE_BINDINGS: dict[ProfileId, dict[str, str]] = {
    "godot.trinity-top-down": {
        "warrior_basic": "warrior_golden_slash",
        "warrior_skill": "warrior_cyan_whirlwind",
        "archer_basic": "archer_arrow_impact",
        "archer_skill": "archer_violet_rain",
        "healer_heal": "healer_restoration_pulse",
        "healer_shield": "healer_golden_shield",
        "healer_resurrection": "healer_blue_resurrection",
        "enemy_melee": "enemy_claw_poison",
        "enemy_caster": "enemy_purple_curse",
    },
    "godot.side-scroll-destination": {
        "warrior_basic": "warrior_crimson_heavy",
        "warrior_skill": "warrior_cyan_whirlwind",
        "archer_basic": "archer_emerald_volley",
        "archer_skill": "archer_violet_rain",
        "healer_heal": "healer_blue_resurrection",
        "healer_shield": "healer_golden_shield",
        "healer_resurrection": "healer_restoration_pulse",
        "enemy_melee": "enemy_red_bite",
        "enemy_caster": "enemy_purple_curse",
    },
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

    effect_ids = tuple(_SOURCES)
    atlas = Image.new(
        "RGBA",
        (
            EFFECT_COLUMNS * EFFECT_FRAME_SIZE,
            ((len(effect_ids) + EFFECT_CANDIDATES_PER_ROW - 1) // EFFECT_CANDIDATES_PER_ROW)
            * EFFECT_FRAME_SIZE,
        ),
        (0, 0, 0, 0),
    )
    candidates: list[dict[str, object]] = []
    slots: list[dict[str, object]] = []
    for row, effect_id in enumerate(effect_ids):
        family, filename, expected_sha = _SOURCES[effect_id]
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
                raise PermissionError(f"generated VFX frame is empty: {effect_id}:{frame}")
            normalized = cell.resize(
                (EFFECT_FRAME_SIZE, EFFECT_FRAME_SIZE), Image.Resampling.NEAREST
            )
            atlas.alpha_composite(
                normalized,
                (
                    ((row % EFFECT_CANDIDATES_PER_ROW) * EFFECT_FRAMES + frame)
                    * EFFECT_FRAME_SIZE,
                    (row // EFFECT_CANDIDATES_PER_ROW) * EFFECT_FRAME_SIZE,
                ),
            )
        candidates.append({
            "effect_id": effect_id,
            "family": family,
            "source_filename": filename,
            "source_sha256": expected_sha,
            "frames": EFFECT_FRAMES,
            "source_grid": [3, 3],
            "alpha_required": True,
        })
        slots.append({
            "effect_id": effect_id,
            "row": row // EFFECT_CANDIDATES_PER_ROW,
            "column_offset": (row % EFFECT_CANDIDATES_PER_ROW) * EFFECT_FRAMES,
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
        "selector": "profile-role-binding-from-three-candidates-per-family-v2",
        "candidate_count": len(candidates),
        "candidates_per_family": 3,
        "bindings": _PROFILE_BINDINGS[profile_id],
        "candidates": candidates,
    }
    atlas_manifest = {
        "schema_version": "khalinos-effect-atlas-v1",
        "profile_id": profile_id,
        "atlas_path": EFFECT_ATLAS_PATH,
        "atlas_sha256": artifact.sha256,
        "frame_size": EFFECT_FRAME_SIZE,
        "columns": EFFECT_COLUMNS,
        "bindings": _PROFILE_BINDINGS[profile_id],
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
        "source_effects": candidates,
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
