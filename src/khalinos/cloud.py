"""Fixed Cloud Run Job dispatch with one immutable run identifier."""

from __future__ import annotations

import os

from google.cloud import run_v2

from khalinos.models import SAFE_RUN_ID


def dispatch_run(run_id: str) -> dict[str, str | bool]:
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("invalid run identifier")
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.environ.get("KHALINOS_REGION", "asia-northeast3")
    job = os.environ.get("KHALINOS_WORKER_JOB", "khalinos-worker")
    name = f"projects/{project}/locations/{region}/jobs/{job}"
    request = run_v2.RunJobRequest(
        name=name,
        overrides={
            "container_overrides": [{"env": [{"name": "KHALINOS_RUN_ID", "value": run_id}]}],
            "task_count": 1,
        },
    )
    operation = run_v2.JobsClient().run_job(request=request)
    operation_name = getattr(getattr(operation, "operation", None), "name", "")
    return {
        "run_id": run_id,
        "project_id": project,
        "region": region,
        "job_name": job,
        "operation_name": operation_name,
        "asynchronous": True,
    }
