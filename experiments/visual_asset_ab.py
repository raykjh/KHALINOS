"""Independent CSS-only versus Nano Banana asset-assisted visual A/B experiment.

This module is deliberately not imported by the production workflow. It proves or rejects
the value of a binary visual-asset path before KHALINOS widens its fixed five-file contract.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from khalinos.agents import AgentTeam, VISUAL_MAKER_INSTRUCTION, _agent
from khalinos.models import ArtifactBundle, ArtifactFile, VisualConcept, canonical_sha256
from khalinos.verification import materialize, verify_bundle


IMAGE_MODEL = "gemini-3.1-flash-lite-image"
ASSET_FILENAME = "visual-asset.png"
PROJECT_ID = "khalinos-agent-20260818"

BRIEF = {
    "project_name": "Threadbound Labyrinth",
    "goal": (
        "Create a polished browser interface for an ancient subterranean turn-based stealth "
        "puzzle. The player studies guard routes, crosses a tiled chamber, recovers a seal, "
        "and escapes. The representative state must make the board, guard intent, red-thread "
        "ability, turn controls, and objective legible without external services."
    ),
    "visual_direction": (
        "A tactile archaeological game interface with carved stone, restrained bronze, deep "
        "shadow, and one vivid red-thread accent. It should feel like a designed game, not a "
        "dashboard, while keeping gameplay information highly readable."
    ),
}

CONCEPT = VisualConcept(
    candidate_id="V1",
    name="Archaeologist's Table",
    design_thesis=(
        "Frame the chamber as a discovered tactical artifact whose carved materials support "
        "clear turn planning and make the red-thread mechanic the memorable focal accent."
    ),
    composition=(
        "Use a dominant central 9 by 9 chamber, a compact objective strip, a guard-intent rail, "
        "and a grounded action bar with strong spatial hierarchy."
    ),
    typography="Use restrained inscription-like display type with highly legible compact UI labels.",
    palette=["obsidian", "limestone", "aged bronze", "oxblood red", "torch amber"],
    interaction_emphasis=(
        "Make the safe route, next guard movement, current turn, and one-use red thread readable "
        "at a glance without obscuring the chamber."
    ),
    anti_goals=["generic SaaS cards", "neon cyberpunk", "decorative text inside imagery"],
)

ASSET_PROMPT = """
Create one polished 16:9 environmental illustration for an ancient subterranean turn-based
stealth puzzle interface. Show a carved stone labyrinth chamber from a slightly elevated
three-quarter view, with restrained aged-bronze fixtures, soft torch ambience, deep readable
shadows, and a single subtle red thread crossing part of the floor. Preserve generous dark
negative space so real HTML game controls and a tile grid can remain legible on top. This is
a supporting environment asset, not a screenshot of an interface. No text, letters, numbers,
icons, buttons, HUD, border, watermark-like mark, or modern object.
""".strip()

ASSET_ASSISTED_INSTRUCTION = f"""
You are the KHALINOS experimental Visual Candidate Maker. Materialize the supplied visual
concept as the same complete five-file browser artifact used by the CSS-only control:
index.html, styles.css, app.js, journey.json, and README.md. A trusted local image named
{ASSET_FILENAME} is supplied alongside the artifact. Integrate it as a supporting environmental
layer using a relative URL, while keeping every label, button, state, tile, route indicator,
and interaction in accessible HTML/CSS/JavaScript. Never bake UI or text into the image.

The page must remain understandable if the asset fails to load. Use only HTML, CSS, inline
SVG, Canvas, vanilla JavaScript, and the trusted local image. No external URLs, packages,
network calls, data URLs, arbitrary code execution, placeholders, or unfinished controls.
Every form control must have an explicit label or aria-label. journey.json must use exactly
{{"journeys":[...]}}. Every journey must have a bounded name and non-empty steps, must omit
criteria, and must use only the
approved typed steps such as {{"click":"CSS selector"}}, {{"press":"Keyboard key"}}, and
{{"assert_text":"visible text"}}. styles.css must include a real @media responsive layout.
Do not use @import. Return only the required ArtifactBundle schema.
""".strip()

PAIRED_STYLE_INSTRUCTION = f"""
You are the KHALINOS experimental Visual Asset Integrator. You receive an already verified
browser product, its exact styles.css, and one trusted local environmental image named
{ASSET_FILENAME}. Return one complete replacement styles.css and nothing else through the
required schema. The HTML, JavaScript, journey, text, controls, and interaction hierarchy are
immutable, so improve atmosphere without redesigning the product.

Use the asset through a relative url('{ASSET_FILENAME}') as a supporting environmental layer.
Maintain excellent grid, guard-intent, red-thread, and control contrast. Keep the existing
archaeological material language and responsive behavior. Include a real @media rule. Do not
use @import, external URLs, packages, data URLs, generated text in imagery, or CSS that hides
functional controls. The page must remain usable if the image fails to load.
""".strip()


class AssetStylePatch(BaseModel):
    styles_css: str = Field(min_length=1000, max_length=50_000)
    rationale: str = Field(min_length=20, max_length=800)


def _generate_asset() -> bytes:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=ASSET_PROMPT,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                aspect_ratio="16:9",
                image_size="1K",
                output_mime_type="image/png",
            ),
        ),
    )
    for candidate in response.candidates or []:
        for part in candidate.content.parts if candidate.content else []:
            if part.inline_data and part.inline_data.mime_type == "image/png":
                return bytes(part.inline_data.data)
    raise RuntimeError("Nano Banana 2 Lite returned no PNG asset")


def _render(bundle: ArtifactBundle, root: Path, *, asset: bytes | None = None):
    product = root / "product"
    evidence_dir = root / "evidence"
    materialize(bundle, product)
    if asset is not None:
        (product / ASSET_FILENAME).write_bytes(asset)
    evidence = verify_bundle(bundle, product, evidence_dir)
    if not evidence.passed or not evidence.screenshot_names:
        raise RuntimeError("candidate failed deterministic rendering: " + " | ".join(evidence.issues))
    screenshot = evidence_dir / evidence.screenshot_names[-1]
    return evidence, screenshot.read_bytes(), screenshot


def _load_bundle(product: Path, summary: str) -> ArtifactBundle:
    names = ["index.html", "styles.css", "app.js", "journey.json", "README.md"]
    return ArtifactBundle(
        revision_summary=summary,
        files=[ArtifactFile(path=name, content=(product / name).read_text(encoding="utf-8")) for name in names],
    )


async def paired_asset_comparison(output_root: Path) -> dict:
    """Isolate image value by changing only CSS on the verified control artifact."""
    asset = (output_root / ASSET_FILENAME).read_bytes()
    css_bundle = _load_bundle(output_root / "A-css-only" / "product", "Recovered CSS-only control")
    files = css_bundle.file_map()
    team = AgentTeam()
    integrator = _agent(
        "khalinos_visual_asset_style_integrator",
        PAIRED_STYLE_INSTRUCTION,
        AssetStylePatch,
        temperature=0.15,
        max_output_tokens=20_000,
    )
    style_patch = await team._run(
        integrator,
        {
            "approved_brief": BRIEF,
            "visual_concept": CONCEPT.model_dump(mode="json"),
            "immutable_index_html": files["index.html"],
            "baseline_styles_css": files["styles.css"],
        },
        AssetStylePatch,
        extra_parts=[types.Part.from_bytes(data=asset, mime_type="image/png")],
    )
    paired_files = dict(files)
    paired_files["styles.css"] = style_patch.styles_css
    paired_bundle = ArtifactBundle(
        revision_summary="Integrate one trusted visual asset through CSS while preserving behavior.",
        files=[ArtifactFile(path=path, content=content) for path, content in paired_files.items()],
    )
    paired_evidence, paired_screenshot, paired_path = await asyncio.to_thread(
        _render, paired_bundle, output_root / "B-paired-asset", asset=asset
    )
    css_path = output_root / "A-css-only" / "evidence" / "journey-01.png"
    css_screenshot = css_path.read_bytes()
    selection = await team.select_visual(
        {
            "approved_brief": BRIEF,
            "shared_visual_contract": CONCEPT.model_dump(mode="json"),
            "eligible_candidates": [
                {"candidate_id": "V1", "arm": "verified CSS-only control"},
                {"candidate_id": "V2", "arm": "same immutable product with Nano Banana 2 Lite asset in CSS"},
            ],
            "controlled_variables": {
                "identical": ["index.html", "app.js", "journey.json", "README.md", "viewport", "journey state"],
                "changed": ["styles.css", ASSET_FILENAME],
            },
            "instruction": (
                "This is a paired comparison. Judge whether the asset-assisted CSS improves the "
                "same product without weakening hierarchy or interaction clarity."
            ),
        },
        [("V1", css_screenshot), ("V2", paired_screenshot)],
    )
    report = {
        "experiment": "KHALINOS paired visual asset A/B",
        "created_at": datetime.now(UTC).isoformat(),
        "production_connected": False,
        "project_id": PROJECT_ID,
        "reasoning_model": os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash"),
        "image_model": IMAGE_MODEL,
        "additional_image_calls": 0,
        "agent_calls": team.call_count,
        "controlled_variables": {
            "identical_file_sha256": {
                path: canonical_sha256({"path": path, "content": files[path]})
                for path in ["index.html", "app.js", "journey.json", "README.md"]
            },
            "only_text_file_changed": "styles.css",
        },
        "style_integrator_rationale": style_patch.rationale,
        "arms": {
            "V1": {
                "name": "CSS-only control",
                "artifact_sha256": canonical_sha256(css_bundle),
                "screenshot": str(css_path),
            },
            "V2": {
                "name": "Paired Nano Banana 2 Lite asset-assisted CSS",
                "artifact_sha256": canonical_sha256(paired_bundle),
                "screenshot": str(paired_path),
                "evidence": paired_evidence.model_dump(mode="json"),
            },
        },
        "independent_visual_selection": selection.model_dump(mode="json"),
    }
    (output_root / "report-paired.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


async def run(output_root: Path) -> dict:
    output_root.mkdir(parents=True, exist_ok=False)
    team = AgentTeam()
    payload = {
        "approved_brief": BRIEF,
        "visual_concept": CONCEPT.model_dump(mode="json"),
        "experiment_arm": "CSS-only control",
    }
    css_bundle = await team.make_visual(payload)

    asset = await asyncio.to_thread(_generate_asset)
    asset_path = output_root / ASSET_FILENAME
    asset_path.write_bytes(asset)
    assisted_agent = _agent(
        "khalinos_visual_asset_experiment_maker",
        ASSET_ASSISTED_INSTRUCTION,
        ArtifactBundle,
        temperature=0.4,
        max_output_tokens=49_152,
    )
    assisted_bundle = await team._run(
        assisted_agent,
        {**payload, "experiment_arm": "Nano Banana 2 Lite asset-assisted"},
        ArtifactBundle,
        extra_parts=[types.Part.from_bytes(data=asset, mime_type="image/png")],
    )

    css_evidence, css_screenshot, css_path = await asyncio.to_thread(
        _render, css_bundle, output_root / "A-css-only"
    )
    assisted_evidence, assisted_screenshot, assisted_path = await asyncio.to_thread(
        _render, assisted_bundle, output_root / "B-asset-assisted", asset=asset
    )
    selection = await team.select_visual(
        {
            "approved_brief": BRIEF,
            "shared_visual_contract": CONCEPT.model_dump(mode="json"),
            "eligible_candidates": [
                {"candidate_id": "V1", "arm": "CSS-only control"},
                {"candidate_id": "V2", "arm": "Nano Banana 2 Lite asset-assisted"},
            ],
            "instruction": (
                "Judge the rendered product, not the presence of an AI-generated image. Penalize "
                "an image if it weakens interaction clarity, responsiveness, or visual cohesion."
            ),
        },
        [("V1", css_screenshot), ("V2", assisted_screenshot)],
    )
    report = {
        "experiment": "KHALINOS visual asset A/B",
        "created_at": datetime.now(UTC).isoformat(),
        "production_connected": False,
        "project_id": PROJECT_ID,
        "reasoning_model": os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash"),
        "image_model": IMAGE_MODEL,
        "image_calls": 1,
        "agent_calls": team.call_count,
        "asset": {"path": str(asset_path), "bytes": len(asset), "prompt": ASSET_PROMPT},
        "arms": {
            "V1": {
                "name": "CSS-only control",
                "artifact_sha256": canonical_sha256(css_bundle),
                "screenshot": str(css_path),
                "evidence": css_evidence.model_dump(mode="json"),
            },
            "V2": {
                "name": "Nano Banana 2 Lite asset-assisted",
                "artifact_sha256": canonical_sha256(assisted_bundle),
                "screenshot": str(assisted_path),
                "evidence": assisted_evidence.model_dump(mode="json"),
            },
        },
        "independent_visual_selection": selection.model_dump(mode="json"),
    }
    (output_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


async def resume_with_bounded_repair(output_root: Path) -> dict:
    """Continue a stopped experiment without regenerating either arm or image asset."""
    asset = (output_root / ASSET_FILENAME).read_bytes()
    css_bundle = _load_bundle(output_root / "A-css-only" / "product", "Recovered CSS-only control")
    failed_bundle = _load_bundle(
        output_root / "B-asset-assisted" / "product", "Recovered failed asset-assisted candidate"
    )
    failed_evidence = verify_bundle(
        failed_bundle,
        output_root / "B-asset-assisted" / "product",
        output_root / "B-asset-assisted" / "evidence",
    )
    if failed_evidence.passed:
        raise RuntimeError("resume expects a deterministically failed asset-assisted candidate")

    team = AgentTeam()
    repair_agent = _agent(
        "khalinos_visual_asset_experiment_repairer",
        ASSET_ASSISTED_INSTRUCTION
        + "\nRepair the supplied failed bundle using only the deterministic issues. Preserve its intended visual composition and the trusted local asset reference.",
        ArtifactBundle,
        temperature=0.1,
        max_output_tokens=49_152,
    )
    repaired_bundle = await team._run(
        repair_agent,
        {
            "approved_brief": BRIEF,
            "visual_concept": CONCEPT.model_dump(mode="json"),
            "failed_bundle": failed_bundle.model_dump(mode="json"),
            "deterministic_evidence": failed_evidence.model_dump(mode="json"),
            "repair_round": 1,
        },
        ArtifactBundle,
        extra_parts=[types.Part.from_bytes(data=asset, mime_type="image/png")],
    )
    repaired_evidence, repaired_screenshot, repaired_path = await asyncio.to_thread(
        _render, repaired_bundle, output_root / "B-asset-assisted-r1", asset=asset
    )
    css_path = output_root / "A-css-only" / "evidence" / "journey-01.png"
    css_screenshot = css_path.read_bytes()
    selection = await team.select_visual(
        {
            "approved_brief": BRIEF,
            "shared_visual_contract": CONCEPT.model_dump(mode="json"),
            "eligible_candidates": [
                {"candidate_id": "V1", "arm": "CSS-only control"},
                {"candidate_id": "V2", "arm": "Nano Banana 2 Lite asset-assisted after one bounded repair"},
            ],
            "instruction": (
                "Judge the rendered product, not the presence of an AI-generated image. Penalize "
                "an image if it weakens interaction clarity, responsiveness, or visual cohesion."
            ),
        },
        [("V1", css_screenshot), ("V2", repaired_screenshot)],
    )
    report = {
        "experiment": "KHALINOS visual asset A/B",
        "created_at": datetime.now(UTC).isoformat(),
        "production_connected": False,
        "continued_without_regeneration": True,
        "project_id": PROJECT_ID,
        "reasoning_model": os.environ.get("KHALINOS_MODEL", "gemini-3.5-flash"),
        "image_model": IMAGE_MODEL,
        "additional_image_calls": 0,
        "agent_calls": team.call_count,
        "initial_asset_candidate_issues": failed_evidence.issues,
        "arms": {
            "V1": {
                "name": "CSS-only control",
                "artifact_sha256": canonical_sha256(css_bundle),
                "screenshot": str(css_path),
            },
            "V2": {
                "name": "Nano Banana 2 Lite asset-assisted after one bounded repair",
                "artifact_sha256": canonical_sha256(repaired_bundle),
                "screenshot": str(repaired_path),
                "evidence": repaired_evidence.model_dump(mode="json"),
            },
        },
        "independent_visual_selection": selection.model_dump(mode="json"),
    }
    (output_root / "report-repaired.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("E:/memory R data/KHALINOS-visual-ab")
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--paired", action="store_true")
    args = parser.parse_args()
    if args.resume and args.paired:
        parser.error("choose only one of --resume or --paired")
    report = asyncio.run(
        paired_asset_comparison(args.output)
        if args.paired
        else resume_with_bounded_repair(args.output)
        if args.resume
        else run(args.output)
    )
    print(json.dumps({
        "output": str(args.output),
        "selected": report["independent_visual_selection"]["selected_candidate_id"],
        "assessments": report["independent_visual_selection"]["assessments"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
