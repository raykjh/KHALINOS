"""Trusted production boundary for bounded Nano Banana browser assets."""

from __future__ import annotations

import base64
import hashlib
import os
import struct
import time

from google import genai
from google.genai import errors, types

from khalinos.models import ArtifactAsset, UserBrief, VisualConcept


IMAGE_MODEL = os.environ.get("KHALINOS_IMAGE_MODEL", "gemini-3.1-flash-lite-image")
ASSET_PATH = "assets/visual-foundation.png"
MAX_ASSET_BYTES = 2_500_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TRANSIENT_MAX_RETRIES = 2


def png_dimensions(payload: bytes) -> tuple[int, int]:
    if len(payload) < 24 or not payload.startswith(PNG_SIGNATURE) or payload[12:16] != b"IHDR":
        raise ValueError("visual asset must be a valid PNG with an IHDR header")
    width, height = struct.unpack(">II", payload[16:24])
    if not 256 <= width <= 2048 or not 256 <= height <= 2048:
        raise ValueError("visual asset dimensions must stay within 256..2048 pixels")
    if width * height > 4_000_000:
        raise ValueError("visual asset pixel count exceeds the approved bound")
    return width, height


def trusted_png_asset(payload: bytes) -> ArtifactAsset:
    if not 1_024 <= len(payload) <= MAX_ASSET_BYTES:
        raise ValueError("visual asset size is outside the approved 1 KB..2.5 MB bound")
    width, height = png_dimensions(payload)
    return ArtifactAsset(
        path=ASSET_PATH,
        data_base64=base64.b64encode(payload).decode("ascii"),
        sha256=hashlib.sha256(payload).hexdigest(),
        width=width,
        height=height,
    )


def asset_prompt(
    brief: UserBrief,
    concept: VisualConcept,
    feedback: tuple[str, ...] = (),
) -> str:
    repair = ""
    if feedback:
        repair = (
            "\nThe previous candidate was rejected for these exact gate findings: "
            + "; ".join(feedback)
            + ". Correct those findings without changing the approved concept.\n"
        )
    return f"""
Create one polished 16:9 supporting environmental illustration for an interactive product.

Approved product goal (design context only):
{brief.goal}

Approved visual concept:
Palette: {', '.join(concept.palette)}
Anti-goals: {'; '.join(concept.anti_goals)}

Translate only the physical environment, material language, atmosphere, and palette into the
image. Do not reproduce the concept name, product name, labels, route names, or interface
composition. The image is a supporting visual layer, never a screenshot or interface. Preserve generous
negative space and restrained contrast so trusted accessible controls and text remain legible
above it. Do not include text, letters, numbers, logos, icons, buttons, HUD elements, borders,
maps with labels, diagrams, readable glyph sequences, watermarks, signatures, or instructions.
Do not include runes, inscriptions, carvings, symbols, signage, interface-like geometry, or
decorative markings of any kind, even when they seem abstract or non-linguistic. If the goal
mentions screens, routes, controls, maps, or labels, do not visualize those elements; generate
only the unmarked physical environment behind them. Any text-like or interface-like mark makes
the asset ineligible. Avoid centered emblems, concentric circles, connected nodes, grids,
selection wheels, diagram-like symmetry, framed panels, or isolated geometric focal objects.
Prefer an irregular, continuous physical landscape with several natural depth layers and no
single object that could be mistaken for a control or HUD element.{repair}Do not add product features or content outside the
approved goal and concept. Return one PNG image.
""".strip()


def _generate_with_transient_retry(client, prompt: str, *, sleep=time.sleep, aspect_ratio: str = "16:9"):
    for attempt in range(TRANSIENT_MAX_RETRIES + 1):
        try:
            return client.models.generate_content(
                model=IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size="1K",
                        output_mime_type="image/png",
                    ),
                ),
            )
        except (errors.ClientError, errors.ServerError) as exc:
            code = getattr(exc, "code", 0)
            transient = code == 429 or 500 <= code <= 599
            if not transient or attempt >= TRANSIENT_MAX_RETRIES:
                raise
            base_delay = 35 if code == 429 else 10
            sleep(base_delay * (2**attempt))
    raise AssertionError("unreachable transient retry state")


def generate_visual_asset(
    brief: UserBrief,
    concept: VisualConcept,
    feedback: tuple[str, ...] = (),
) -> ArtifactAsset:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "khalinos-agent-20260818")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    client = genai.Client(vertexai=True, project=project, location=location)
    response = _generate_with_transient_retry(client, asset_prompt(brief, concept, feedback))
    for candidate in response.candidates or []:
        for part in candidate.content.parts if candidate.content else []:
            if part.inline_data and part.inline_data.mime_type == "image/png":
                return trusted_png_asset(bytes(part.inline_data.data))
    raise RuntimeError("Nano Banana returned no PNG visual asset")
