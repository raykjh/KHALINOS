"""Cloud Run Job entry point."""

from __future__ import annotations

import asyncio
import json
import os

from khalinos.agents import AgentTeam
from khalinos.models import SAFE_RUN_ID
from khalinos.storage import CloudRunStore
from khalinos.projects import CloudProjectStore
from khalinos.registry import APPROVED_TOOLPACKS
from khalinos.run_router import execute_authorized_run


def main() -> int:
    run_id = os.environ.get("KHALINOS_RUN_ID", "")
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("KHALINOS_RUN_ID is missing or invalid")
    store = CloudRunStore()
    execution_id = os.environ.get("CLOUD_RUN_EXECUTION", "")
    if execution_id:
        record = store.read_record(run_id)
        store.update(record.model_copy(update={"cloud_execution_id": execution_id}))
    result = asyncio.run(execute_authorized_run(
        run_id,
        store=store,
        team=AgentTeam(),
        registry=APPROVED_TOOLPACKS,
        project_store=CloudProjectStore(),
    ))
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    return 0 if result.status.value == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
