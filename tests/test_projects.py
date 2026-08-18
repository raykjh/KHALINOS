from __future__ import annotations

import pytest

from khalinos.models import ProjectRecord, RunRecord, RunStatus
from khalinos.projects import LocalProjectStore


def project(owner: str = "owner-a") -> ProjectRecord:
    return ProjectRecord(
        project_id="1" * 32,
        owner_id=owner,
        display_name="Verified project",
        latest_run_id="2" * 32,
        latest_status=RunStatus.QUEUED,
    )


def test_project_library_is_owner_bound(tmp_path) -> None:
    store = LocalProjectStore(tmp_path)
    store.prepare(project())
    assert [item.project_id for item in store.list_owned("owner-a")] == ["1" * 32]
    assert store.list_owned("owner-b") == []
    with pytest.raises(PermissionError):
        store.read_owned("1" * 32, "owner-b")


def test_verified_run_updates_latest_checkpoint(tmp_path) -> None:
    store = LocalProjectStore(tmp_path)
    store.prepare(project())
    run = RunRecord(
        run_id="3" * 32,
        status=RunStatus.PASSED,
        brief_sha256="4" * 64,
        message="Passed.",
        owner_id="owner-a",
        project_id="1" * 32,
        completed_receipt_ids=["QR-one"],
    )
    updated = store.update_checkpoint(run, "5" * 64)
    assert updated.latest_run_id == run.run_id
    assert updated.latest_checkpoint_sha256 == "5" * 64
    assert updated.latest_receipt_ids == ["QR-one"]
