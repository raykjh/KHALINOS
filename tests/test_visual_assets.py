from __future__ import annotations

import base64
import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest
from google.genai import errors

from khalinos.models import ArtifactAsset, ArtifactBundle, ArtifactFile, UserBrief, VisualAssetGate, VisualConcept
from khalinos.storage import LocalRunStore
from khalinos.verification import materialize, verify_bundle
from khalinos.visual_assets import ASSET_PATH, _generate_with_transient_retry, asset_prompt, trusted_png_asset


class FakeImageModels:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def generate_content(self, **_kwargs):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeImageClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.models = FakeImageModels(outcomes)


def valid_png(width: int = 256, height: int = 256) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    rows = b"".join(
        b"\x00" + bytes(value for x in range(width) for value in (x, y, (x * 31 + y * 17) % 256, 255))
        for y in range(height)
    )
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def visual_bundle(*, reference_asset: bool = True) -> ArtifactBundle:
    image = (
        f'<img src="{ASSET_PATH}" data-khalinos-asset="visual-foundation" alt="">'
        if reference_asset
        else ""
    )
    values = {
        "index.html": f"<!doctype html><html><head><link rel='stylesheet' href='styles.css'></head><body>{image}<button aria-label='Go'>Go</button><p>Ready</p><script src='app.js'></script></body></html>",
        "styles.css": "img{position:fixed;inset:0;width:100%;height:100%;object-fit:cover}button{position:relative}@media(max-width:600px){button{width:100%}}",
        "app.js": "document.querySelector('button').addEventListener('click',()=>{});",
        "journey.json": json.dumps({"journeys": [{"name": "render", "steps": [{"click": "button"}, {"assert_text": "Ready"}]}]}),
        "README.md": "# Visual product\n\nRun from a local static server.",
    }
    return ArtifactBundle(
        revision_summary="Trusted visual asset render candidate",
        files=[ArtifactFile(path=path, content=content) for path, content in values.items()],
        assets=[trusted_png_asset(valid_png())],
    )


def test_trusted_png_asset_binds_bytes_dimensions_and_digest() -> None:
    payload = valid_png()
    asset = trusted_png_asset(payload)
    assert asset.path == ASSET_PATH
    assert asset.sha256 == hashlib.sha256(payload).hexdigest()
    assert (asset.width, asset.height) == (256, 256)
    assert asset.bytes() == payload


def test_asset_prompt_forbids_ui_and_abstract_glyph_escape_hatches() -> None:
    brief = UserBrief(
        project_name="Route Screen",
        goal="Create a polished route-selection screen with a strong environmental identity.",
        acceptance_criteria=["The route screen is visible.", "The visual style is coherent."],
        authorized_output_files=["index.html"],
    )
    concept = VisualConcept(
        candidate_id="V1",
        name="Ancient Route",
        design_thesis="A restrained physical environment supports an accessible route decision surface.",
        composition="A wide environmental field leaves controlled negative space for the trusted interface.",
        typography="Clear display headings pair with compact readable interface labels.",
        palette=["stone", "midnight", "copper"],
        interaction_emphasis="The trusted interface remains visually dominant over the supporting environment.",
        anti_goals=["generic cards", "ornamental clutter"],
    )
    prompt = asset_prompt(brief, concept)
    assert "do not visualize those elements" in prompt
    assert "runes, inscriptions, carvings, symbols" in prompt
    assert "only the unmarked physical environment" in prompt
    assert "centered emblems, concentric circles, connected nodes, grids" in prompt

    repaired = asset_prompt(brief, concept, ("contains_interface_elements",))
    assert "previous candidate was rejected" in repaired
    assert "contains_interface_elements" in repaired


def test_image_generation_retries_only_bounded_transient_errors() -> None:
    success = object()
    client = FakeImageClient([
        errors.ServerError(500, {"error": {"message": "internal"}}),
        errors.ClientError(429, {"error": {"message": "limited"}}),
        success,
    ])
    delays: list[int] = []

    assert _generate_with_transient_retry(client, "prompt", sleep=delays.append) is success
    assert client.models.calls == 3
    assert delays == [10, 70]


def test_image_generation_does_not_retry_nontransient_client_errors() -> None:
    client = FakeImageClient([errors.ClientError(400, {"error": {"message": "bad request"}})])
    delays: list[int] = []

    with pytest.raises(errors.ClientError):
        _generate_with_transient_retry(client, "prompt", sleep=delays.append)
    assert client.models.calls == 1
    assert delays == []


def test_artifact_asset_rejects_dimension_or_digest_tampering() -> None:
    payload = valid_png()
    encoded = base64.b64encode(payload).decode("ascii")
    digest = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError, match="dimensions"):
        ArtifactAsset(path=ASSET_PATH, data_base64=encoded, sha256=digest, width=512, height=256)
    with pytest.raises(ValueError, match="digest"):
        ArtifactAsset(path=ASSET_PATH, data_base64=encoded, sha256="0" * 64, width=256, height=256)


def test_visual_asset_gate_cannot_approve_detected_text_or_reject_clean_asset() -> None:
    with pytest.raises(ValueError, match="approval"):
        VisualAssetGate(
            candidate_id="V1",
            approved=True,
            contains_text_or_glyphs=True,
            contains_interface_elements=False,
            contains_logo_or_watermark=False,
            issues=["Readable title detected."],
            rationale="The raw image visibly contains a readable title and is not a safe background.",
        )
    with pytest.raises(ValueError, match="approval"):
        VisualAssetGate(
            candidate_id="V1",
            approved=False,
            contains_text_or_glyphs=False,
            contains_interface_elements=False,
            contains_logo_or_watermark=False,
            rationale="The raw image contains no forbidden content and cannot be rejected by this gate.",
        )


def test_rendered_visual_verifier_requires_the_asset_to_load_visibly(tmp_path: Path) -> None:
    bundle = visual_bundle()
    product = tmp_path / "product"
    evidence_dir = tmp_path / "evidence"
    materialize(bundle, product)
    evidence = verify_bundle(bundle, product, evidence_dir)
    assert evidence.passed, evidence.issues
    assert evidence.issues == []
    assert evidence.checks["trusted_visual_assets_loaded"]
    assert evidence.screenshot_names == ["journey-01.png"]
    assert (evidence_dir / "journey-01.png").is_file()


def test_asset_file_without_rendered_asset_element_cannot_pass(tmp_path: Path) -> None:
    bundle = visual_bundle(reference_asset=False)
    product = tmp_path / "product"
    materialize(bundle, product)
    evidence = verify_bundle(bundle, product, tmp_path / "evidence")
    assert not evidence.passed
    assert not evidence.checks["trusted_visual_assets_loaded"]
    assert any("trusted visual asset element" in issue for issue in evidence.issues)


def test_verified_bundle_archive_round_trips_the_binary_asset(tmp_path: Path) -> None:
    bundle = visual_bundle()
    store = LocalRunStore(tmp_path)
    snapshot = store.put_bundle_archive("a" * 32, bundle)
    restored = store.read_bundle_archive(snapshot)
    assert restored.assets[0].sha256 == bundle.assets[0].sha256
    assert restored.assets[0].bytes() == bundle.assets[0].bytes()
