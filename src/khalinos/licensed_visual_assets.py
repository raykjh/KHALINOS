"""License-aware selection and atlas composition for user-supplied game art.

The original asset library stays outside the repository.  This module records
only source identifiers, deterministic selection rules, transformations, and
receipts; generated games may embed only the selected, composed atlas.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
from typing import Literal

from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, model_validator

from khalinos.models import ArtifactAsset


AETHERAI_LICENSE_ID = "AetherAI-Free-Asset-License-2026-06-29"
AETHERAI_SOURCE_URL = "https://www.aetherforgeai.com/ko/free-assets"
LICENSED_ATLAS_PATH = "assets/licensed-art-atlas.png"
ASSET_SELECTION_PATH = "KHALINOS_ASSET_SELECTION.json"
STYLE_COMPOSITION_PATH = "KHALINOS_STYLE_COMPOSITION.json"
LICENSED_ATLAS_MANIFEST_PATH = "KHALINOS_LICENSED_ATLAS.json"
LICENSE_RECEIPT_PATH = "KHALINOS_LICENSE_RECEIPT.json"
ATLAS_COLUMNS = 4
ATLAS_ROWS = 4
ATLAS_CELL_SIZE = 128
ATLAS_SIZE = ATLAS_COLUMNS * ATLAS_CELL_SIZE
EXPECTED_CATALOG_SIZE = 384

_BUNDLED_PROFILE_DIRECTORIES: dict[str, str] = {
    "godot.trinity-top-down": "trinity",
    "godot.side-scroll-destination": "side-scroll",
}

ProfileId = Literal["godot.trinity-top-down", "godot.side-scroll-destination"]
AssetGrade = Literal["A", "B", "C"]


# These are source UUID filenames, not redistributed asset bytes.  The same
# source may serve both profiles under different role bindings.
_CURATED_ROLE_PATHS: dict[str, dict[str, str]] = {
    "godot.trinity-top-down": {
        "warrior": "32px/characters/d6312bea-5364-42ea-b5a4-48433ccd2ff8.png",
        "archer": "32px/characters/523051e1-580e-4c49-8499-d86b210a7bf7.png",
        "priest": "32px/characters/efb14f22-de8d-480f-843a-b01a4b840e04.png",
        "goblin": "32px/monsters/af94efc0-4332-4598-9896-184cd1fc4cb0.png",
        "orc": "32px/monsters/ab4476fa-ad31-4cbf-b703-eafe8e2d55a9.png",
        "sweep_icon": "40px-k-rpg/swords/215ea63c-8d19-4888-afe1-3b96da040443.png",
        "volley_icon": "40px-k-rpg/bows/820b42b9-b76e-4084-8ce4-e91b826590d0.png",
        "prayer_icon": "40px-k-rpg/staves/b1561b1e-6a71-4d15-92a9-dc7d7eb00dce.png",
    },
    "godot.side-scroll-destination": {
        "warrior": "32px/characters/d6312bea-5364-42ea-b5a4-48433ccd2ff8.png",
        "archer": "32px/characters/523051e1-580e-4c49-8499-d86b210a7bf7.png",
        "priest": "32px/characters/efb14f22-de8d-480f-843a-b01a4b840e04.png",
        "enemy_scout": "32px/monsters/348ea202-cfd2-4855-9118-53b58a424663.png",
        "enemy_brute": "32px/monsters/ab4476fa-ad31-4cbf-b703-eafe8e2d55a9.png",
        "enemy_beast": "32px/monsters/e1b0e92d-2ab1-4f1f-b72c-ae02fbe987ac.png",
        "enemy_caster": "32px/monsters/af94efc0-4332-4598-9896-184cd1fc4cb0.png",
        "destination": "32px/buildings/bf281c75-61f4-4625-a215-fc21fb95d83e.png",
        "tree": "32px/props/216b29a8-ef14-4954-bb92-3201ccfa024e.png",
        "rock": "32px/props/ad83878c-a5d4-4f1d-8b6b-89d379604d6f.png",
        "sword_icon": "40px-k-rpg/swords/215ea63c-8d19-4888-afe1-3b96da040443.png",
        "bow_icon": "40px-k-rpg/bows/820b42b9-b76e-4084-8ce4-e91b826590d0.png",
        "heal_icon": "40px-k-rpg/staves/b1561b1e-6a71-4d15-92a9-dc7d7eb00dce.png",
    },
}


# Manual visual review rejected these candidates from the dark-expedition
# direction.  They remain preserved in the source library and are not deleted.
_GRADE_C_PREFIXES = {
    "08ce32d2",  # bright novelty character
    "97c3baf7",  # exaggerated cartoon character
    "23f647a3",  # luminous fairy silhouette
    "df351150",  # bright pink creature
    "88de8d7f",  # toy-like slime
}


class GradedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    relative_path: str
    source_url: str = Field(pattern=r"^https://")
    style: Literal["32px", "32px-pastel", "40px-k-rpg"]
    category: str
    grade: AssetGrade
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(ge=1)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    selected_roles: tuple[str, ...] = ()
    selected_profiles: tuple[ProfileId, ...] = ()
    rationale: str

    @model_validator(mode="after")
    def canonical_bindings(self) -> "GradedAsset":
        if tuple(sorted(set(self.selected_roles))) != self.selected_roles:
            raise ValueError("selected asset roles must be unique and sorted")
        if tuple(sorted(set(self.selected_profiles))) != self.selected_profiles:
            raise ValueError("selected asset profiles must be unique and sorted")
        if self.grade == "A" and not self.selected_roles:
            raise ValueError("grade-A asset must have an explicit profile role")
        if self.grade != "A" and (self.selected_roles or self.selected_profiles):
            raise ValueError("only grade-A assets may be bound into profiles")
        return self


class SelectedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    asset_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    source_url: str = Field(pattern=r"^https://")
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_relative_path: str
    atlas_region: tuple[int, int, int, int]


class LicensedArtBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: Literal["khalinos-licensed-art-bundle-v1"] = "khalinos-licensed-art-bundle-v1"
    profile_id: ProfileId
    selected_assets: tuple[SelectedAsset, ...]
    atlas: ArtifactAsset
    selection_manifest: dict[str, object]
    style_manifest: dict[str, object]
    atlas_manifest: dict[str, object]
    license_receipt: dict[str, object]

    def text_files(self) -> dict[str, str]:
        payloads = {
            ASSET_SELECTION_PATH: self.selection_manifest,
            STYLE_COMPOSITION_PATH: self.style_manifest,
            LICENSED_ATLAS_MANIFEST_PATH: self.atlas_manifest,
            LICENSE_RECEIPT_PATH: self.license_receipt,
        }
        return {
            path: json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            for path, value in payloads.items()
        }


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_relative(path: Path, root: Path) -> str:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    parts = PurePosixPath(relative).parts
    if not parts or ".." in parts:
        raise PermissionError("licensed asset escaped its approved input root")
    return relative


def grade_asset_library(root: Path) -> tuple[GradedAsset, ...]:
    """Grade every PNG while preserving all originals and rejecting ambiguity."""

    source_root = root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"licensed asset input root is unavailable: {source_root}")
    role_bindings: dict[str, list[tuple[ProfileId, str]]] = {}
    for raw_profile, roles in _CURATED_ROLE_PATHS.items():
        profile: ProfileId = raw_profile  # type: ignore[assignment]
        for role, relative in roles.items():
            role_bindings.setdefault(relative, []).append((profile, role))

    graded: list[GradedAsset] = []
    candidates = [
        path
        for style_root in (
            source_root / "32px",
            source_root / "32px-pastel",
            source_root / "40px-k-rpg",
        )
        for path in style_root.rglob("*.png")
    ]
    for path in sorted(candidates):
        relative = _normalize_relative(path, source_root)
        parts = PurePosixPath(relative).parts
        if len(parts) < 3 or parts[0] not in {"32px", "32px-pastel", "40px-k-rpg"}:
            raise PermissionError(f"licensed asset uses an unapproved library layout: {relative}")
        payload = path.read_bytes()
        try:
            with Image.open(io.BytesIO(payload)) as image:
                width, height = image.size
                image.verify()
        except Exception as exc:
            raise ValueError(f"licensed asset is not a decodable image: {relative}") from exc
        bindings = sorted(role_bindings.get(relative, []))
        if bindings:
            grade: AssetGrade = "A"
            rationale = "manually selected for a concrete profile role after contact-sheet review"
        elif path.stem[:8] in _GRADE_C_PREFIXES:
            grade = "C"
            rationale = "preserved but excluded from the restrained dark-expedition direction"
        else:
            grade = "B"
            rationale = "compatible reserve; not admitted into the current bounded atlas"
        graded.append(GradedAsset(
            asset_id=path.stem,
            relative_path=relative,
            source_url=f"https://cdn.aetherforgeai.com/assets/{path.name}",
            style=parts[0],
            category=parts[-2],
            grade=grade,
            sha256=_sha256(payload),
            byte_size=len(payload),
            width=width,
            height=height,
            selected_roles=tuple(sorted({role for _, role in bindings})),
            selected_profiles=tuple(sorted({profile for profile, _ in bindings})),
            rationale=rationale,
        ))
    expected = EXPECTED_CATALOG_SIZE
    if len(graded) != expected:
        raise PermissionError(f"licensed input catalog changed: expected {expected} PNGs, found {len(graded)}")
    missing = sorted(set(role_bindings) - {item.relative_path for item in graded})
    if missing:
        raise FileNotFoundError("curated licensed assets are missing: " + ", ".join(missing))
    return tuple(graded)


def grading_manifest(entries: tuple[GradedAsset, ...]) -> dict[str, object]:
    counts = {grade: sum(item.grade == grade for item in entries) for grade in ("A", "B", "C")}
    return {
        "schema_version": "khalinos-asset-grading-v1",
        "provider": "AetherAI",
        "license_id": AETHERAI_LICENSE_ID,
        "source_url": AETHERAI_SOURCE_URL,
        "total_assets": len(entries),
        "grade_counts": counts,
        "assets": [item.model_dump(mode="json") for item in entries],
    }


def _selected_for_profile(entries: tuple[GradedAsset, ...], profile_id: ProfileId) -> tuple[tuple[str, GradedAsset], ...]:
    by_path = {item.relative_path: item for item in entries}
    selected: list[tuple[str, GradedAsset]] = []
    for role, relative in _CURATED_ROLE_PATHS[profile_id].items():
        item = by_path[relative]
        if item.grade != "A" or profile_id not in item.selected_profiles or role not in item.selected_roles:
            raise PermissionError(f"asset grading does not authorize {profile_id}:{role}")
        selected.append((role, item))
    if len(selected) > ATLAS_COLUMNS * ATLAS_ROWS:
        raise PermissionError("licensed atlas exceeds its bounded slot count")
    return tuple(selected)


def _compose_atlas(root: Path, selected: tuple[tuple[str, GradedAsset], ...]) -> tuple[ArtifactAsset, tuple[SelectedAsset, ...]]:
    atlas = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))
    receipts: list[SelectedAsset] = []
    for index, (role, entry) in enumerate(selected):
        source_path = (root.resolve() / Path(*PurePosixPath(entry.relative_path).parts)).resolve()
        if not source_path.is_relative_to(root.resolve()) or not source_path.is_file():
            raise PermissionError("selected licensed asset escaped its approved input root")
        payload = source_path.read_bytes()
        if _sha256(payload) != entry.sha256:
            raise PermissionError(f"selected asset changed after grading: {entry.relative_path}")
        with Image.open(io.BytesIO(payload)) as source:
            sprite = source.convert("RGBA")
        contained = ImageOps.contain(
            sprite,
            (ATLAS_CELL_SIZE - 12, ATLAS_CELL_SIZE - 12),
            method=Image.Resampling.NEAREST,
        )
        left = (index % ATLAS_COLUMNS) * ATLAS_CELL_SIZE
        top = (index // ATLAS_COLUMNS) * ATLAS_CELL_SIZE
        x = left + (ATLAS_CELL_SIZE - contained.width) // 2
        y = top + (ATLAS_CELL_SIZE - contained.height) // 2
        atlas.alpha_composite(contained, (x, y))
        region = (left, top, ATLAS_CELL_SIZE, ATLAS_CELL_SIZE)
        receipts.append(SelectedAsset(
            role=role,
            asset_id=entry.asset_id,
            source_url=entry.source_url,
            source_sha256=entry.sha256,
            source_relative_path=entry.relative_path,
            atlas_region=region,
        ))
    output = io.BytesIO()
    atlas.save(output, format="PNG", optimize=False)
    payload = output.getvalue()
    artifact = ArtifactAsset(
        path=LICENSED_ATLAS_PATH,
        data_base64=base64.b64encode(payload).decode("ascii"),
        sha256=_sha256(payload),
        width=ATLAS_SIZE,
        height=ATLAS_SIZE,
    )
    return artifact, tuple(receipts)


def build_licensed_art_bundle(root: Path, profile_id: ProfileId) -> LicensedArtBundle:
    """Execute Asset Selector -> Style Composer -> Godot Atlas -> License Receipt."""

    entries = grade_asset_library(root)
    selected_pairs = _selected_for_profile(entries, profile_id)
    atlas, selected = _compose_atlas(root, selected_pairs)
    selection = {
        "schema_version": "khalinos-asset-selection-v1",
        "profile_id": profile_id,
        "selector": "catalog-grade-and-curated-role-binding-v2",
        "candidate_catalog_size": len(entries),
        "candidate_catalog_sha256": _canonical_sha256(
            [item.model_dump(mode="json") for item in entries]
        ),
        "candidate_style_counts": {
            style: sum(item.style == style for item in entries)
            for style in ("32px", "32px-pastel", "40px-k-rpg")
        },
        "assets": [item.model_dump(mode="json") for item in selected],
    }
    style = {
        "schema_version": "khalinos-style-composition-v1",
        "profile_id": profile_id,
        "style_id": "dark-expedition-pixel-v1",
        "reserve_styles": ["32px", "32px-pastel", "40px-k-rpg"],
        "palette": ["#172027", "#2f4a3b", "#6e7f4d", "#d6a743", "#e6ded0"],
        "rules": [
            "adult-readable silhouettes",
            "muted environment with warm objective accents",
            "green hostile family distinct from heroes",
            "nearest-neighbor pixel scaling",
            "no standalone source-asset redistribution",
        ],
        "selected_asset_sha256": _canonical_sha256(selection["assets"]),
    }
    atlas_manifest = {
        "schema_version": "khalinos-licensed-atlas-v1",
        "profile_id": profile_id,
        "atlas_path": LICENSED_ATLAS_PATH,
        "atlas_sha256": atlas.sha256,
        "columns": ATLAS_COLUMNS,
        "rows": ATLAS_ROWS,
        "cell_size": ATLAS_CELL_SIZE,
        "slots": [item.model_dump(mode="json") for item in selected],
    }
    receipt = {
        "schema_version": "khalinos-license-receipt-v1",
        "provider": "AetherAI",
        "license_id": AETHERAI_LICENSE_ID,
        "license_last_updated": "2026-06-29",
        "license_source_url": AETHERAI_SOURCE_URL,
        "credit_required": False,
        "standalone_asset_pack_redistribution_allowed": False,
        "included_as_part_of_game": True,
        "profile_id": profile_id,
        "source_assets": [
            {
                "asset_id": item.asset_id,
                "source_url": item.source_url,
                "source_sha256": item.source_sha256,
                "role": item.role,
                "operations": ["atlas-composition", "nearest-neighbor-scale", "game-integration"],
            }
            for item in selected
        ],
        "output_atlas_path": LICENSED_ATLAS_PATH,
        "output_atlas_sha256": atlas.sha256,
        "selection_sha256": _canonical_sha256(selection),
        "style_sha256": _canonical_sha256(style),
        "passed": True,
    }
    return LicensedArtBundle(
        profile_id=profile_id,
        selected_assets=selected,
        atlas=atlas,
        selection_manifest=selection,
        style_manifest=style,
        atlas_manifest=atlas_manifest,
        license_receipt=receipt,
    )


def _load_bundled_licensed_art_bundle(root: Path, profile_id: ProfileId) -> LicensedArtBundle:
    """Load and revalidate one bounded, game-integrated atlas preset."""

    def load_json(name: str) -> dict[str, object]:
        path = root / name
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PermissionError(f"bundled licensed-art receipt is unavailable: {path}") from exc
        if not isinstance(value, dict):
            raise PermissionError(f"bundled licensed-art receipt must be an object: {path}")
        return value

    selection = load_json(ASSET_SELECTION_PATH)
    style = load_json(STYLE_COMPOSITION_PATH)
    atlas_manifest = load_json(LICENSED_ATLAS_MANIFEST_PATH)
    receipt = load_json(LICENSE_RECEIPT_PATH)
    for name, value in (
        ("selection", selection),
        ("style", style),
        ("atlas", atlas_manifest),
        ("license", receipt),
    ):
        if value.get("profile_id") != profile_id:
            raise PermissionError(f"bundled {name} receipt belongs to another profile")

    raw_assets = selection.get("assets")
    raw_slots = atlas_manifest.get("slots")
    if not isinstance(raw_assets, list) or raw_assets != raw_slots:
        raise PermissionError("bundled licensed-art selection does not match its atlas slots")
    try:
        selected = tuple(SelectedAsset.model_validate(item) for item in raw_assets)
    except (TypeError, ValueError) as exc:
        raise PermissionError("bundled licensed-art selection is invalid") from exc
    if not selected or len(selected) > ATLAS_COLUMNS * ATLAS_ROWS:
        raise PermissionError("bundled licensed-art selection exceeds its bounded slot count")

    atlas_path = root / "licensed-art-atlas.png"
    try:
        payload = atlas_path.read_bytes()
    except OSError as exc:
        raise PermissionError(f"bundled licensed-art atlas is unavailable: {atlas_path}") from exc
    atlas_sha256 = _sha256(payload)
    if (
        atlas_manifest.get("atlas_path") != LICENSED_ATLAS_PATH
        or atlas_manifest.get("atlas_sha256") != atlas_sha256
        or atlas_manifest.get("columns") != ATLAS_COLUMNS
        or atlas_manifest.get("rows") != ATLAS_ROWS
        or atlas_manifest.get("cell_size") != ATLAS_CELL_SIZE
    ):
        raise PermissionError("bundled licensed-art atlas does not match its manifest")
    if (
        receipt.get("provider") != "AetherAI"
        or receipt.get("license_id") != AETHERAI_LICENSE_ID
        or receipt.get("included_as_part_of_game") is not True
        or receipt.get("standalone_asset_pack_redistribution_allowed") is not False
        or receipt.get("passed") is not True
        or receipt.get("output_atlas_path") != LICENSED_ATLAS_PATH
        or receipt.get("output_atlas_sha256") != atlas_sha256
        or receipt.get("selection_sha256") != _canonical_sha256(selection)
        or receipt.get("style_sha256") != _canonical_sha256(style)
    ):
        raise PermissionError("bundled licensed-art license chain is invalid")

    atlas = ArtifactAsset(
        path=LICENSED_ATLAS_PATH,
        data_base64=base64.b64encode(payload).decode("ascii"),
        sha256=atlas_sha256,
        width=ATLAS_SIZE,
        height=ATLAS_SIZE,
    )
    return LicensedArtBundle(
        profile_id=profile_id,
        selected_assets=selected,
        atlas=atlas,
        selection_manifest=selection,
        style_manifest=style,
        atlas_manifest=atlas_manifest,
        license_receipt=receipt,
    )


def bundled_licensed_art_bundle(profile_id: ProfileId) -> LicensedArtBundle:
    """Resolve the qualified profile atlas shipped as part of generated games."""

    directory = _BUNDLED_PROFILE_DIRECTORIES[profile_id]
    root = Path(__file__).resolve().parent / "assets" / "licensed" / directory
    return _load_bundled_licensed_art_bundle(root, profile_id)


def configured_licensed_art_bundle(profile_id: ProfileId) -> LicensedArtBundle:
    """Resolve approved art from an external catalog or the qualified preset.

    An explicit external root rebuilds from the full source catalog and fails
    closed if that catalog changed.  Cloud and other clean environments use the
    bounded profile atlas plus its checked-in selection, style, and license
    receipts; invalid presets also fail closed instead of reverting to generic
    art.
    """

    raw_root = os.environ.get("KHALINOS_LICENSED_ASSET_ROOT", "").strip()
    if raw_root:
        return build_licensed_art_bundle(Path(raw_root), profile_id)
    return bundled_licensed_art_bundle(profile_id)
