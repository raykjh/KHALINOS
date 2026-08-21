"""Run one real, isolated Cloud qualification of the Godot visual workflow."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from khalinos.agents import AgentTeam
from khalinos.godot_visual_workflow import execute_godot_visual_run
from khalinos.models import RunRecord, RunStatus, UserBrief, canonical_sha256
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.storage import CloudRunStore


async def qualify() -> int:
    run_id = uuid4().hex
    toolpack = APPROVED_TOOLPACKS.select(
        project_kind="godot",
        work_mode="new_product_build",
        requested_toolpack_id="godot.visual-prototype",
    )
    binding = toolpack.binding()
    brief = UserBrief(
        project_name="The Threefold Passage",
        goal=(
            "Create a presentation-ready Godot visual prototype for an ancient underground route puzzle. "
            "Establish the arrival and route-selection screens with a distinctive atmospheric visual direction. "
            "This qualification does not claim finished gameplay."
        ),
        constraints=[
            "Keep every user-facing label in English.",
            "Do not claim combat, puzzle logic, physics, save systems, or finished gameplay.",
            "Use only the approved Godot Visual Prototype ToolPack output surface.",
        ],
        acceptance_criteria=[
            "The arrival screen and its visual direction are visible in a real Godot render.",
            "The route-selection screen is loadable through the declared navigation topology.",
        ],
        max_quests=3,
        max_repairs_per_quest=0,
        toolpack_binding=binding,
        authorized_output_files=list(toolpack.manifest.output.authorized_paths),
    )
    record = RunRecord(
        run_id=run_id,
        status=RunStatus.QUEUED,
        brief_sha256=canonical_sha256(brief),
        toolpack_binding=binding,
        message="Isolated Godot visual-prototype Cloud qualification queued.",
        owner_id="khalinos-qualification",
        work_mode="new_product_build",
    )
    store = CloudRunStore()
    store.create(record, brief)
    result = await execute_godot_visual_run(
        run_id,
        store=store,
        team=AgentTeam(),
        registry=APPROVED_TOOLPACKS,
    )
    print(json.dumps({
        "run_id": run_id,
        "status": result.status.value,
        "message": result.message,
        "model_calls": result.model_calls,
        "receipt_ids": result.completed_receipt_ids,
    }, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.status == RunStatus.PASSED else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(qualify()))
