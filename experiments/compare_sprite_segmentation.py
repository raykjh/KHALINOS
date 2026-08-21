"""Independent background-segmentation bake-off for Nano Banana sprite sources.

This experiment intentionally does not import into or alter the KHALINOS ToolPack path.
Raw sources, model caches, cutouts, montages, and reports live under an external output root.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import time
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field

from khalinos.models import UserBrief, VisualConcept
from khalinos.sprite_assets import SpriteSlot, normalize_sprite_source, sprite_source_prompt
from khalinos.visual_assets import _generate_with_transient_retry


SLOTS = (
    SpriteSlot(sprite_id="warrior", kind="hero", label="Warrior", visual_role="armored melee tank with a two-handed sword", slot_index=0),
    SpriteSlot(sprite_id="archer", kind="hero", label="Archer", visual_role="mobile ranged damage hero with a longbow", slot_index=1),
    SpriteSlot(sprite_id="priest", kind="hero", label="Priest", visual_role="support healer with a staff and pale ceremonial robes", slot_index=2),
    SpriteSlot(sprite_id="goblin", kind="enemy", label="Goblin", visual_role="small hostile melee enemy carrying a crude blade", slot_index=3),
    SpriteSlot(sprite_id="orc", kind="enemy", label="Orc", visual_role="large hostile bruiser carrying a heavy axe", slot_index=4),
)
MODELS = ("u2netp", "isnet-anime", "birefnet-general-lite")


class ModelVisualScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    background_removal: int = Field(ge=0, le=10)
    silhouette_completeness: int = Field(ge=0, le=10)
    fine_detail_preservation: int = Field(ge=0, le=10)
    edge_quality: int = Field(ge=0, le=10)
    failure_count: int = Field(ge=0, le=5)
    concise_findings: list[str] = Field(min_length=1, max_length=5)


class VisualVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scores: list[ModelVisualScore] = Field(min_length=3, max_length=3)
    winner: str
    runner_up: str
    recommendation: str


def approved_context() -> tuple[UserBrief, VisualConcept]:
    brief = UserBrief(
        project_name="Trinity Survivors",
        goal=(
            "Create a ten-minute 2D top-down Godot survival roguelike where a warrior, archer, "
            "and priest move as one team against goblins, orcs, and trolls."
        ),
        acceptance_criteria=["Heroes remain readable at gameplay scale.", "Enemies remain visually distinct."],
        authorized_output_files=["assets/sprite-atlas.png"],
    )
    concept = VisualConcept(
        candidate_id="V1",
        name="Verdant Ruins",
        design_thesis="Polished painterly fantasy sprites with strong silhouettes, restrained texture, and coherent warm rim lighting.",
        composition="Each isolated character reads clearly at compact top-down gameplay scale.",
        typography="No typography appears inside generated sprite sources.",
        palette=["moss green", "weathered bronze", "warm parchment", "ember orange"],
        interaction_emphasis="Hero roles and enemy threat levels remain immediately distinguishable.",
        anti_goals=["photorealism", "chibi proportions", "text", "scenery", "multiple characters"],
    )
    return brief, concept


def extract_png(response) -> bytes:
    for candidate in response.candidates or []:
        for part in candidate.content.parts if candidate.content else []:
            if part.inline_data and part.inline_data.mime_type == "image/png":
                return bytes(part.inline_data.data)
    raise RuntimeError("Nano Banana returned no PNG")


def generate_sources(root: Path, *, minimum_interval: float = 35.0) -> None:
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    brief, concept = approved_context()
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "khalinos-agent-20260818"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    )
    calls: list[dict[str, object]] = []
    last_call = 0.0
    for slot in SLOTS:
        destination = raw / f"{slot.sprite_id}.png"
        if destination.exists():
            continue
        delay = minimum_interval - (time.monotonic() - last_call)
        if delay > 0:
            time.sleep(delay)
        prompt = sprite_source_prompt(brief, concept, slot)
        started = time.perf_counter()
        response = _generate_with_transient_retry(client, prompt, aspect_ratio="1:1")
        last_call = time.monotonic()
        payload = extract_png(response)
        destination.write_bytes(payload)
        image = Image.open(io.BytesIO(payload))
        calls.append({
            "sprite_id": slot.sprite_id,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "dimensions": list(image.size),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "prompt": prompt,
        })
    (root / "generation.json").write_text(json.dumps(calls, indent=2), encoding="utf-8")


def alpha_metrics(image: Image.Image) -> dict[str, object]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    values = list(alpha.getdata())
    opaque = sum(value > 16 for value in values)
    soft = sum(16 < value < 239 for value in values)
    width, height = rgba.size
    border_values = []
    border_values.extend(alpha.crop((0, 0, width, 8)).getdata())
    border_values.extend(alpha.crop((0, height - 8, width, height)).getdata())
    border_values.extend(alpha.crop((0, 8, 8, height - 8)).getdata())
    border_values.extend(alpha.crop((width - 8, 8, width, height - 8)).getdata())
    return {
        "dimensions": [width, height],
        "bbox": list(bbox) if bbox else None,
        "coverage": round(opaque / (width * height), 6),
        "soft_alpha_fraction": round(soft / (width * height), 6),
        "border_alpha_fraction": round(sum(value > 16 for value in border_values) / len(border_values), 6),
    }


def checkerboard(size: tuple[int, int]) -> Image.Image:
    result = Image.new("RGB", size, "#d7d7d7")
    draw = ImageDraw.Draw(result)
    tile = 24
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill="#f2f2f2")
    return result


def build_montage(root: Path) -> None:
    cell = 300
    label = 36
    columns = 1 + len(MODELS)
    canvas = Image.new("RGB", (columns * cell, len(SLOTS) * (cell + label)), "white")
    draw = ImageDraw.Draw(canvas)
    headings = ("raw",) + MODELS
    for column, heading in enumerate(headings):
        draw.text((column * cell + 8, 8), heading, fill="black")
    for row, slot in enumerate(SLOTS):
        y = row * (cell + label)
        draw.text((8, y + label - 24), slot.sprite_id, fill="black")
        paths = (root / "raw" / f"{slot.sprite_id}.png",) + tuple(
            root / "cutouts" / model / f"{slot.sprite_id}.png" for model in MODELS
        )
        for column, path in enumerate(paths):
            image = Image.open(path).convert("RGBA")
            image.thumbnail((cell - 16, cell - 16), Image.Resampling.LANCZOS)
            background = checkerboard((cell, cell))
            offset = ((cell - image.width) // 2, (cell - image.height) // 2)
            background.paste(image, offset, image)
            canvas.paste(background, (column * cell, y + label))
    canvas.save(root / "comparison-montage.png", optimize=True)


def normalize_outputs(root: Path) -> None:
    for model in MODELS:
        output_dir = root / "normalized" / model
        output_dir.mkdir(parents=True, exist_ok=True)
        for slot in SLOTS:
            payload = (root / "cutouts" / model / f"{slot.sprite_id}.png").read_bytes()
            normalized = normalize_sprite_source(payload, slot)
            (output_dir / f"{slot.sprite_id}.png").write_bytes(normalized.bytes())

    cell = 256
    label = 30
    canvas = Image.new("RGB", (len(MODELS) * cell, len(SLOTS) * (cell + label)), "white")
    draw = ImageDraw.Draw(canvas)
    for column, model in enumerate(MODELS):
        draw.text((column * cell + 8, 8), model, fill="black")
    for row, slot in enumerate(SLOTS):
        y = row * (cell + label)
        draw.text((8, y + label - 22), slot.sprite_id, fill="black")
        for column, model in enumerate(MODELS):
            image = Image.open(root / "normalized" / model / f"{slot.sprite_id}.png").convert("RGBA")
            background = checkerboard((cell, cell))
            background.paste(image, (0, 0), image)
            canvas.paste(background, (column * cell, y + label))
    canvas.save(root / "normalized-montage.png", optimize=True)


def compare(root: Path) -> None:
    from rembg import new_session, remove

    report: dict[str, object] = {"models": {}, "samples": [slot.sprite_id for slot in SLOTS]}
    for model in MODELS:
        output_dir = root / "cutouts" / model
        output_dir.mkdir(parents=True, exist_ok=True)
        session_started = time.perf_counter()
        session = new_session(model)
        session_seconds = time.perf_counter() - session_started
        records = []
        for slot in SLOTS:
            source = root / "raw" / f"{slot.sprite_id}.png"
            destination = output_dir / source.name
            started = time.perf_counter()
            payload = remove(source.read_bytes(), session=session, decontaminate=True)
            elapsed = time.perf_counter() - started
            destination.write_bytes(payload)
            records.append({
                "sprite_id": slot.sprite_id,
                "elapsed_seconds": round(elapsed, 3),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                **alpha_metrics(Image.open(io.BytesIO(payload))),
            })
        report["models"][model] = {
            "session_seconds": round(session_seconds, 3),
            "records": records,
        }
    (root / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    build_montage(root)


def verify(root: Path) -> None:
    montage = (root / "comparison-montage.png").read_bytes()
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "khalinos-agent-20260818"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    )
    response = client.models.generate_content(
        model=os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash"),
        contents=[
            types.Part.from_text(text=(
                "Act as an independent visual verifier. The montage has five character rows and four columns: "
                "raw, u2netp, isnet-anime, and birefnet-general-lite. Score only the three segmentation outputs. "
                "Inspect whether the baked checkerboard/background was removed, whether the complete single character "
                "including weapons, hands, feet, capes, hair, horns, and staff was retained, and whether edges contain "
                "halos, holes, clipping, or residue. A model counts as a failure on a row if it leaves a broad background "
                "or loses a material character part. Prefer a robust result across all five rows over a single excellent row."
            )),
            types.Part.from_bytes(data=montage, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VisualVerdict,
            temperature=0,
        ),
    )
    verdict = VisualVerdict.model_validate_json(response.text)
    (root / "visual-verdict.json").write_text(verdict.model_dump_json(indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "compare", "normalize", "verify", "all"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    if args.command in {"generate", "all"}:
        generate_sources(args.root)
    if args.command in {"compare", "all"}:
        compare(args.root)
    if args.command in {"normalize", "all"}:
        normalize_outputs(args.root)
    if args.command in {"verify", "all"}:
        verify(args.root)


if __name__ == "__main__":
    main()
