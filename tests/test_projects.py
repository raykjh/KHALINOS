from __future__ import annotations

import pytest

from khalinos.models import ArchiveSnapshot, MaterialDescriptor, ProjectRecord, RunRecord, RunStatus
from khalinos.projects import LocalProjectStore


def project(owner: str = "owner-a") -> ProjectRecord:
    return ProjectRecord(
        project_id="1" * 32,
        owner_id=owner,
        display_name="Verified project",
        latest_run_id="2" * 32,
        latest_status=RunStatus.QUEUED,
    )


def snapshot() -> ArchiveSnapshot:
    names = ["index.html", "styles.css", "app.js", "journey.json", "README.md"]
    return ArchiveSnapshot(
        bucket="bucket",
        object_name="runs/verified/final/source.zip",
        generation=1,
        sha256="6" * 64,
        size_bytes=500,
        entry_count=5,
        uncompressed_size_bytes=400,
        materials=[MaterialDescriptor(filename=name, relative_path=name, size_bytes=1) for name in names],
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
    source = snapshot()
    updated = store.update_checkpoint(run, "5" * 64, source)
    assert updated.latest_run_id == run.run_id
    assert updated.latest_checkpoint_sha256 == "5" * 64
    assert updated.latest_receipt_ids == ["QR-one"]
    assert updated.source_snapshot == source
