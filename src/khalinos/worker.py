"""Cloud Run Job entry point."""

from __future__ import annotations

import asyncio
import json
import os

from khalinos.agents import AgentTeam
from khalinos.models import SAFE_RUN_ID
from khalinos.storage import CloudRunStore
from khalinos.workflow import execute_run


def main() -> int:
    run_id = os.environ.get("KHALINOS_RUN_ID", "")
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("KHALINOS_RUN_ID is missing or invalid")
    result = asyncio.run(execute_run(run_id, store=CloudRunStore(), team=AgentTeam()))
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    return 0 if result.status.value == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

