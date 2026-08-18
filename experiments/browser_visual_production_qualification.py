"""Paid isolated qualification for the production Browser visual-asset path."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from khalinos.agents import AgentTeam
from khalinos.browser_toolpack import BROWSER_PRODUCT_MANIFEST, BROWSER_PRODUCT_TOOLPACK
from khalinos.models import RunRecord, RunStatus, UserBrief, canonical_sha256
from khalinos.storage import LocalRunStore
from khalinos.toolpacks import ToolPackRegistry
from khalinos.workflow import execute_run


async def qualify(output_root: Path) -> dict:
    run_id = uuid4().hex
    store = LocalRunStore(output_root)
    brief = UserBrief(
        project_name="Ancient Wayfinding Signal",
        goal=(
            "Create a polished offline browser scene that helps a user compare three ancient "
            "wayfinding signals and confirm one safe route. The scene must visibly combine one "
            "supporting environmental image with accessible HTML controls. Choosing a route must "
            "update a clear selected-route status, and the complete layout must remain usable at "
            "a 320 pixel mobile viewport. Do not add network services, external dependencies, or "
            "text inside generated imagery."
        ),
        constraints=[
            "Use English UI text.",
            "Keep all labels and state in accessible HTML rather than the generated image.",
            "Use only the trusted local visual asset supplied by the Browser ToolPack.",
        ],
        acceptance_criteria=[
            "Choosing a route updates the visible selected-route status.",
            "The complete interface remains usable at a 320 pixel viewport.",
        ],
        max_quests=2,
        max_repairs_per_quest=2,
        toolpack_binding=BROWSER_PRODUCT_TOOLPACK.binding(),
        authorized_output_files=list(BROWSER_PRODUCT_MANIFEST.output.authorized_paths),
    )
    store.create(
        RunRecord(
            run_id=run_id,
            status=RunStatus.QUEUED,
            brief_sha256=canonical_sha256(brief),
            toolpack_binding=BROWSER_PRODUCT_TOOLPACK.binding(),
            message="Isolated production visual qualification queued.",
        ),
        brief,
    )
    result = await execute_run(
        run_id,
        store=store,
        team=AgentTeam(),
        registry=ToolPackRegistry([BROWSER_PRODUCT_TOOLPACK]),
    )
    run_root = output_root / "runs" / run_id
    report = {
        "qualification": "browser Nano Banana production visual path",
        "run": result.model_dump(mode="json"),
        "toolpack_binding": BROWSER_PRODUCT_TOOLPACK.binding().model_dump(mode="json"),
    }
    for name, relative in {
        "visual_selection_receipt": "visuals/selection_receipt.json",
        "final_artifact_manifest": "final/artifact_manifest.json",
    }.items():
        target = run_root / relative
        report[name] = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
    report_path = output_root / "qualification-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("E:/memory R data/KHALINOS-browser-visual-production-qualification"),
    )
    args = parser.parse_args()
    report = asyncio.run(qualify(args.output_root))
    print(json.dumps({
        "status": report["run"]["status"],
        "run_id": report["run"]["run_id"],
        "model_calls": report["run"]["model_calls"],
        "report": str(args.output_root / "qualification-report.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
