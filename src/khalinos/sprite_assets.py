"""Trusted Nano Banana sprite-atlas generation and deterministic normalization."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps
from google import genai
from pydantic import BaseModel, ConfigDict, Field, model_validator

from khalinos.models import ArtifactAsset, UserBrief, VisualConcept
from khalinos.visual_assets import IMAGE_MODEL, _generate_with_transient_retry


SPRITE_ATLAS_PATH = "assets/sprite-atlas.png"
SPRITE_ATLAS_MANIFEST_PATH = "KHALINOS_SPRITE_ATLAS.json"
ATLAS_COLUMNS = 4
ATLAS_ROWS = 3
ATLAS_WIDTH = 1024
ATLAS_HEIGHT = 768
CELL_WIDTH = ATLAS_WIDTH // ATLAS_COLUMNS
CELL_HEIGHT = ATLAS_HEIGHT // ATLAS_ROWS
MAX_SPRITE_ATLAS_BYTES = 2_500_000
MAX_SPRITE_SOURCE_BYTES = 2_500_000
SOURCE_SIZE = 1024
COMPOSED_SPRITE_SIZE = 208
MAX_SOURCE_NORMALIZATION_ATTEMPTS = 2
SPRITE_SEGMENTATION_MODEL_ID = "isnet-anime"
SPRITE_SEGMENTATION_MODEL_VERSION = "rembg-2.0.81-onnx"
SPRITE_SEGMENTATION_MODEL_URL = (
    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx"
)
SPRITE_SEGMENTATION_MODEL_SHA256 = "f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99"
SPRITE_SEGMENTATION_MODEL_BYTES = 176_069_933


class SpriteSegmentationContract(BaseModel):
    """Exact local model and inference settings admitted by the Sprite Asset boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-sprite-segmentation-v1"] = "khalinos-sprite-segmentation-v1"
    model_id: Literal["isnet-anime"] = SPRITE_SEGMENTATION_MODEL_ID
    model_version: Literal["rembg-2.0.81-onnx"] = SPRITE_SEGMENTATION_MODEL_VERSION
    model_url: Literal[SPRITE_SEGMENTATION_MODEL_URL] = SPRITE_SEGMENTATION_MODEL_URL
    model_sha256: Literal[SPRITE_SEGMENTATION_MODEL_SHA256] = SPRITE_SEGMENTATION_MODEL_SHA256
    model_bytes: Literal[176_069_933] = SPRITE_SEGMENTATION_MODEL_BYTES
    license_id: Literal["Apache-2.0"] = "Apache-2.0"
    input_width: Literal[1024] = SOURCE_SIZE
    input_height: Literal[1024] = SOURCE_SIZE
    execution_provider: Literal["CPUExecutionProvider"] = "CPUExecutionProvider"
    decontaminate_edges: Literal[True] = True
    network_allowed: Literal[False] = False

    def sha256(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


SPRITE_SEGMENTATION_CONTRACT = SpriteSegmentationContract()


def approved_sprite_model_path() -> Path:
    configured = os.environ.get("KHALINOS_SPRITE_SEGMENTATION_MODEL_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    home = Path(os.environ.get("REMBG_HOME", Path.home() / ".rembg")).expanduser().resolve()
    return home / "models" / SPRITE_SEGMENTATION_MODEL_ID / f"{SPRITE_SEGMENTATION_MODEL_ID}.onnx"


def verify_sprite_segmentation_model(path: Path | None = None) -> Path:
    candidate = (path or approved_sprite_model_path()).resolve()
    if not candidate.is_file():
        raise RuntimeError(f"approved sprite segmentation model is missing: {candidate}")
    if candidate.stat().st_size != SPRITE_SEGMENTATION_CONTRACT.model_bytes:
        raise RuntimeError("sprite segmentation model byte size changed after approval")
    digest = hashlib.sha256()
    with candidate.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != SPRITE_SEGMENTATION_CONTRACT.model_sha256:
        raise RuntimeError("sprite segmentation model digest changed after approval")
    return candidate


class ApprovedSpriteSegmenter:
    """Fail-closed IS-Net Anime inference over one digest-verified local ONNX weight."""

    def __init__(self, model_path: Path | None = None) -> None:
        self.model_path = verify_sprite_segmentation_model(model_path)
        try:
            from rembg import new_session
        except ImportError as exc:
            raise RuntimeError("approved sprite segmentation runtime is not installed") from exc
        expected_model_dir = self.model_path.parent
        if expected_model_dir.name != SPRITE_SEGMENTATION_MODEL_ID or expected_model_dir.parent.name != "models":
            raise RuntimeError("approved sprite model must use the bounded rembg model directory layout")
        previous_home = os.environ.get("REMBG_HOME")
        os.environ["REMBG_HOME"] = str(expected_model_dir.parent.parent)
        try:
            self._session = new_session(
                SPRITE_SEGMENTATION_MODEL_ID,
                providers=[SPRITE_SEGMENTATION_CONTRACT.execution_provider],
            )
        finally:
            if previous_home is None:
                os.environ.pop("REMBG_HOME", None)
            else:
                os.environ["REMBG_HOME"] = previous_home

    def __call__(self, payload: bytes) -> bytes:
        try:
            from rembg import remove
        except ImportError as exc:
            raise RuntimeError("approved sprite segmentation runtime is not installed") from exc
        return remove(
            payload,
            session=self._session,
            decontaminate=SPRITE_SEGMENTATION_CONTRACT.decontaminate_edges,
        )


class SpriteSlot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sprite_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    kind: Literal["hero", "enemy"]
    label: str = Field(min_length=1, max_length=40)
    visual_role: str = Field(min_length=2, max_length=80)
    slot_index: int = Field(ge=0, lt=ATLAS_COLUMNS * ATLAS_ROWS)

    def region(self) -> tuple[int, int, int, int]:
        return (
            (self.slot_index % ATLAS_COLUMNS) * CELL_WIDTH,
            (self.slot_index // ATLAS_COLUMNS) * CELL_HEIGHT,
            CELL_WIDTH,
            CELL_HEIGHT,
        )


class SpriteAtlasPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["godot.sprite-atlas.v1"] = "godot.sprite-atlas.v1"
    columns: Literal[4] = ATLAS_COLUMNS
    rows: Literal[3] = ATLAS_ROWS
    width: Literal[1024] = ATLAS_WIDTH
    height: Literal[768] = ATLAS_HEIGHT
    slots: tuple[SpriteSlot, ...] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def canonical_slots(self) -> "SpriteAtlasPlan":
        ids = [item.sprite_id for item in self.slots]
        indices = [item.slot_index for item in self.slots]
        if len(ids) != len(set(ids)):
            raise ValueError("sprite IDs must be unique")
        if indices != list(range(len(self.slots))):
            raise ValueError("sprite slots must be contiguous and ordered from zero")
        return self

    def manifest(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "atlas_path": SPRITE_ATLAS_PATH,
            "columns": self.columns,
            "rows": self.rows,
            "width": self.width,
            "height": self.height,
            "slots": [
                {**item.model_dump(mode="json"), "region": list(item.region())}
                for item in self.slots
            ],
        }


class NormalizedSprite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sprite_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    data_base64: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: Literal[256] = CELL_WIDTH
    height: Literal[256] = CELL_HEIGHT

    def bytes(self) -> bytes:
        return base64.b64decode(self.data_base64)


def sprite_source_prompt(
    brief: UserBrief,
    concept: VisualConcept,
    slot: SpriteSlot,
    feedback: tuple[str, ...] = (),
) -> str:
    repair = "\nPrevious rejected-source issue to correct:\n" + "\n".join(f"- {item}" for item in feedback) if feedback else ""
    return f"""
Create one production-quality static gameplay character sprite for a Godot 2D game.

Approved product context:
{brief.goal}

Selected visual concept:
Palette: {', '.join(concept.palette)}
Material and style: {concept.design_thesis}
Anti-goals: {'; '.join(concept.anti_goals)}

Character: {slot.kind} {slot.label}
Visual role: {slot.visual_role}

Use a fully transparent background. If transparency cannot be emitted, use one perfectly
flat solid #FF00FF background. Place exactly one isolated, centered, full-body top-down or
high three-quarter-view character on a square canvas. The opaque character silhouette must
occupy 45% to 65% of the canvas width and height, with a continuous high-contrast outer contour
and at least 15% empty margin on every side. Never make the character tiny, faint, translucent,
low-contrast against the background, or mostly hidden by effects.
Do not use #FF00FF on the character. Keep the selected concept's scale, outline language,
lighting, and materials so separately generated characters form one coherent roster. Do not
add text, letters, numbers, labels, logos, icons, HUD, cards, frames, watermarks, signatures,
extra characters, scenery, ground, detached equipment, animation frames, or cropped body
parts. Render the character body and equipment as solid opaque materials: never draw a
transparency checkerboard, checker/grid texture, cutout mosaic, see-through body surface,
floor shadow, magic circle, halo, platform, base, or ring beneath the feet. Return one square
PNG and nothing else.{repair}
""".strip()


def _background_distance(pixel: tuple[int, int, int, int], background: tuple[int, int, int, int]) -> int:
    return sum((pixel[index] - background[index]) ** 2 for index in range(3))


def _remove_cell_backgrounds(image: Image.Image) -> None:
    """Remove bounded per-cell flat/near-flat backgrounds without hiding extra subjects."""

    pixels = image.load()
    for index in range(ATLAS_COLUMNS * ATLAS_ROWS):
        left = (index % ATLAS_COLUMNS) * CELL_WIDTH
        top = (index // ATLAS_COLUMNS) * CELL_HEIGHT
        samples = [
            pixels[left + 2, top + 2],
            pixels[left + CELL_WIDTH - 3, top + 2],
            pixels[left + 2, top + CELL_HEIGHT - 3],
            pixels[left + CELL_WIDTH - 3, top + CELL_HEIGHT - 3],
        ]
        for y in range(top, top + CELL_HEIGHT):
            for x in range(left, left + CELL_WIDTH):
                pixel = pixels[x, y]
                if min(_background_distance(pixel, sample) for sample in samples) <= 42 * 42:
                    pixels[x, y] = (pixel[0], pixel[1], pixel[2], 0)


def _remove_source_background(image: Image.Image) -> None:
    """Remove only background regions connected to the source image boundary."""

    pixels = image.load()
    corner_samples = [
        pixels[2, 2],
        pixels[image.width - 3, 2],
        pixels[2, image.height - 3],
        pixels[image.width - 3, image.height - 3],
    ]
    width, height = image.size
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def add(x: int, y: int) -> None:
        index = y * width + x
        if visited[index]:
            return
        visited[index] = 1
        queue.append((x, y))

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(1, height - 1):
        add(0, y)
        add(width - 1, y)

    while queue:
        x, y = queue.popleft()
        current = pixels[x, y]
        pixels[x, y] = (current[0], current[1], current[2], 0)
        for neighbor_x, neighbor_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= neighbor_x < width and 0 <= neighbor_y < height):
                continue
            index = neighbor_y * width + neighbor_x
            if visited[index]:
                continue
            neighbor = pixels[neighbor_x, neighbor_y]
            locally_continuous = _background_distance(neighbor, current) <= 14 * 14
            corner_like = min(_background_distance(neighbor, sample) for sample in corner_samples) <= 48 * 48
            if neighbor[3] <= 8 or locally_continuous or corner_like:
                visited[index] = 1
                queue.append((neighbor_x, neighbor_y))


def _retain_central_subject(image: Image.Image, slot: SpriteSlot) -> None:
    """Keep the central character component and nearby detached equipment only."""

    width, height = image.size
    alpha = image.getchannel("A").tobytes()
    visited = bytearray(width * height)
    components: list[dict[str, object]] = []
    for start in range(width * height):
        if visited[start] or alpha[start] <= 16:
            continue
        visited[start] = 1
        pending: deque[int] = deque([start])
        pixels: list[int] = []
        min_x = max_x = start % width
        min_y = max_y = start // width
        while pending:
            index = pending.popleft()
            pixels.append(index)
            x = index % width
            y = index // width
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for neighbor in (index - 1, index + 1, index - width, index + width):
                if neighbor < 0 or neighbor >= width * height or visited[neighbor] or alpha[neighbor] <= 16:
                    continue
                neighbor_x = neighbor % width
                neighbor_y = neighbor // width
                if abs(neighbor_x - x) + abs(neighbor_y - y) != 1:
                    continue
                visited[neighbor] = 1
                pending.append(neighbor)
        components.append({
            "pixels": pixels,
            "area": len(pixels),
            "bbox": (min_x, min_y, max_x + 1, max_y + 1),
            "center": ((min_x + max_x + 1) / 2.0, (min_y + max_y + 1) / 2.0),
            "touches_boundary": min_x < 16 or min_y < 16 or max_x >= width - 16 or max_y >= height - 16,
        })

    candidates = [
        item for item in components
        if not item["touches_boundary"]
        and int(item["area"]) >= 512
        and width * 0.18 <= item["center"][0] <= width * 0.82
        and height * 0.12 <= item["center"][1] <= height * 0.88
    ]
    if not candidates:
        raise ValueError(f"sprite source {slot.sprite_id} contains no isolated central character")
    primary = max(
        candidates,
        key=lambda item: int(item["area"]) / (
            1.0
            + abs(item["center"][0] - width / 2.0) / width
            + abs(item["center"][1] - height / 2.0) / height
        ),
    )
    left, top, right, bottom = primary["bbox"]
    retention_bounds = (left - 96, top - 96, right + 96, bottom + 96)
    minimum_attachment_area = max(64, int(primary["area"]) // 250)
    kept: list[dict[str, object]] = []
    for item in components:
        item_left, item_top, item_right, item_bottom = item["bbox"]
        near_primary = not (
            item_right < retention_bounds[0]
            or item_left > retention_bounds[2]
            or item_bottom < retention_bounds[1]
            or item_top > retention_bounds[3]
        )
        if item is primary or (
            not item["touches_boundary"]
            and int(item["area"]) >= minimum_attachment_area
            and near_primary
        ):
            kept.append(item)

    retained_alpha = bytearray(width * height)
    for item in kept:
        for index in item["pixels"]:
            retained_alpha[index] = alpha[index]
    image.putalpha(Image.frombytes("L", (width, height), bytes(retained_alpha)))


def normalize_sprite_source(payload: bytes, slot: SpriteSlot) -> NormalizedSprite:
    if not 1_024 <= len(payload) <= MAX_SPRITE_SOURCE_BYTES:
        raise ValueError(f"sprite source {slot.sprite_id} size is outside the approved bound")
    try:
        image = Image.open(io.BytesIO(payload)).convert("RGBA")
    except Exception as exc:
        raise ValueError(f"sprite source {slot.sprite_id} must be a decodable PNG") from exc
    if image.size != (SOURCE_SIZE, SOURCE_SIZE):
        width, height = image.size
        if not (800 <= width <= 1400 and 800 <= height <= 1400 and abs(width / height - 1.0) <= 0.03):
            raise ValueError(f"sprite source {slot.sprite_id} is outside the approved square model-output bound")
        image = ImageOps.fit(image, (SOURCE_SIZE, SOURCE_SIZE), method=Image.Resampling.LANCZOS)
    corners = [image.getpixel(point) for point in ((0, 0), (1023, 0), (0, 1023), (1023, 1023))]
    if not all(pixel[3] <= 8 for pixel in corners):
        _remove_source_background(image)
    _retain_central_subject(image, slot)
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError(f"sprite source {slot.sprite_id} contains no visible character")
    if bbox[0] < 16 or bbox[1] < 16 or bbox[2] > SOURCE_SIZE - 16 or bbox[3] > SOURCE_SIZE - 16:
        raise ValueError(f"sprite source {slot.sprite_id} touches the source boundary")
    nonzero = sum(1 for value in alpha.get_flattened_data() if value > 16)
    coverage = nonzero / (SOURCE_SIZE * SOURCE_SIZE)
    subject_width = bbox[2] - bbox[0]
    subject_height = bbox[3] - bbox[1]
    if not 0.005 <= coverage <= 0.85 or min(subject_width, subject_height) < 80:
        raise ValueError(
            f"sprite source {slot.sprite_id} foreground geometry is outside the approved bound "
            f"(coverage={coverage:.4f}, bbox={subject_width}x{subject_height})"
        )

    subject = image.crop(bbox)
    scale = min(COMPOSED_SPRITE_SIZE / subject.width, COMPOSED_SPRITE_SIZE / subject.height)
    resized = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    subject = subject.resize(resized, Image.Resampling.LANCZOS)
    cell = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    offset = ((CELL_WIDTH - subject.width) // 2, (CELL_HEIGHT - subject.height) // 2)
    cell.alpha_composite(subject, offset)
    output = io.BytesIO()
    cell.save(output, format="PNG", optimize=True)
    normalized = output.getvalue()
    return NormalizedSprite(
        sprite_id=slot.sprite_id,
        data_base64=base64.b64encode(normalized).decode("ascii"),
        sha256=hashlib.sha256(normalized).hexdigest(),
    )


def compose_sprite_atlas(plan: SpriteAtlasPlan, sprites: tuple[NormalizedSprite, ...]) -> ArtifactAsset:
    expected = [slot.sprite_id for slot in plan.slots]
    actual = [sprite.sprite_id for sprite in sprites]
    if actual != expected:
        raise ValueError("normalized sprites must exactly match the approved slot order")
    image = Image.new("RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))
    for slot, sprite in zip(plan.slots, sprites, strict=True):
        cell = Image.open(io.BytesIO(sprite.bytes())).convert("RGBA")
        if cell.size != (CELL_WIDTH, CELL_HEIGHT):
            raise ValueError(f"normalized sprite {slot.sprite_id} changed dimensions")
        left, top, _, _ = slot.region()
        image.alpha_composite(cell, (left, top))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return normalize_sprite_atlas(output.getvalue(), plan)


def normalize_sprite_atlas(payload: bytes, plan: SpriteAtlasPlan) -> ArtifactAsset:
    if not 1_024 <= len(payload) <= MAX_SPRITE_ATLAS_BYTES:
        raise ValueError("sprite atlas size is outside the approved 1 KB..2.5 MB bound")
    try:
        image = Image.open(io.BytesIO(payload)).convert("RGBA")
    except Exception as exc:
        raise ValueError("sprite atlas must be a decodable PNG") from exc
    if image.size != (plan.width, plan.height):
        width, height = image.size
        aspect_error = abs((width / height) - (plan.width / plan.height))
        if not (800 <= width <= 1600 and 700 <= height <= 1400 and aspect_error <= 0.03):
            raise ValueError(
                f"sprite atlas source size {width}x{height} is outside the approved 4:3 model-output bound"
            )
        image = ImageOps.fit(
            image,
            (plan.width, plan.height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

    corners = [image.getpixel((x, y)) for x, y in ((0, 0), (image.width - 1, 0), (0, image.height - 1), (image.width - 1, image.height - 1))]
    transparent = all(pixel[3] <= 8 for pixel in corners)
    if not transparent:
        _remove_cell_backgrounds(image)

    alpha = image.getchannel("A")
    occupied_slots: list[int] = []
    for index in range(ATLAS_COLUMNS * ATLAS_ROWS):
        left = (index % ATLAS_COLUMNS) * CELL_WIDTH
        top = (index // ATLAS_COLUMNS) * CELL_HEIGHT
        cell = alpha.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))
        bbox = cell.getbbox()
        assigned = index < len(plan.slots)
        if not assigned:
            if bbox is not None:
                raise ValueError(f"unassigned sprite atlas cell {index + 1} is not empty")
            continue
        if bbox is None:
            raise ValueError(f"assigned sprite atlas cell {index + 1} is empty")
        margin_x = max(8, int(CELL_WIDTH * 0.06))
        margin_y = max(8, int(CELL_HEIGHT * 0.06))
        if bbox[0] < margin_x or bbox[1] < margin_y or bbox[2] > CELL_WIDTH - margin_x or bbox[3] > CELL_HEIGHT - margin_y:
            raise ValueError(f"sprite in cell {index + 1} touches its protected gutter")
        nonzero = sum(1 for value in cell.get_flattened_data() if value > 16)
        coverage = nonzero / (CELL_WIDTH * CELL_HEIGHT)
        if not 0.04 <= coverage <= 0.72:
            raise ValueError(f"sprite coverage in cell {index + 1} is outside the approved bound")
        occupied_slots.append(index)
    if occupied_slots != list(range(len(plan.slots))):
        raise ValueError("sprite atlas occupancy does not match its approved slot plan")

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    normalized = output.getvalue()
    return ArtifactAsset(
        path=SPRITE_ATLAS_PATH,
        data_base64=base64.b64encode(normalized).decode("ascii"),
        sha256=hashlib.sha256(normalized).hexdigest(),
        width=plan.width,
        height=plan.height,
    )


def generate_sprite_atlas(
    brief: UserBrief,
    concept: VisualConcept,
    plan: SpriteAtlasPlan,
    feedback: tuple[str, ...] = (),
    on_model_call: Callable[[], None] | None = None,
    segment_source: Callable[[bytes], bytes] | None = None,
) -> ArtifactAsset:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "khalinos-agent-20260818")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    client = genai.Client(vertexai=True, project=project, location=location)
    segment = segment_source or ApprovedSpriteSegmenter()
    sprites: list[NormalizedSprite] = []
    for slot in plan.slots:
        last_failure: Exception | None = None
        for attempt in range(1, MAX_SOURCE_NORMALIZATION_ATTEMPTS + 1):
            attempt_feedback = feedback
            if last_failure is not None:
                attempt_feedback = (*feedback, (
                    f"The previous {slot.label} source was rejected by deterministic normalization: "
                    f"{last_failure}. Generate one larger opaque central full-body character with "
                    "clear empty margins and no platform or background residue."
                ))
            if on_model_call is not None:
                on_model_call()
            response = _generate_with_transient_retry(
                client,
                sprite_source_prompt(brief, concept, slot, attempt_feedback),
                aspect_ratio="1:1",
            )
            payload = next(
                (
                    bytes(part.inline_data.data)
                    for candidate in response.candidates or []
                    for part in (candidate.content.parts if candidate.content else [])
                    if part.inline_data and part.inline_data.mime_type == "image/png"
                ),
                None,
            )
            if payload is None:
                last_failure = RuntimeError("Nano Banana returned no PNG")
                continue
            try:
                segmented = segment(payload)
                sprite = normalize_sprite_source(segmented, slot)
                break
            except Exception as exc:
                last_failure = exc
        else:
            raise RuntimeError(
                f"sprite source {slot.sprite_id} failed its approved IS-Net Anime segmentation "
                f"and normalization after {MAX_SOURCE_NORMALIZATION_ATTEMPTS} bounded attempts: "
                f"{last_failure}"
            ) from last_failure
        sprites.append(sprite)
    return compose_sprite_atlas(plan, tuple(sprites))
