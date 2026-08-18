"""Owner-bound KHALINOS project library and verified checkpoint records."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from google.cloud import firestore

from khalinos.models import ProjectRecord, RunRecord, RunStatus, utc_now


class ProjectStore(Protocol):
    def prepare(self, record: ProjectRecord) -> None: ...
    def read_owned(self, project_id: str, owner_id: str) -> ProjectRecord: ...
    def list_owned(self, owner_id: str) -> list[ProjectRecord]: ...
    def update_checkpoint(self, run: RunRecord, checkpoint_sha256: str) -> ProjectRecord: ...


class LocalProjectStore:
    def __init__(self, root: Path):
        self.root = root.resolve() / "projects"

    def _path(self, project_id: str) -> Path:
        return self.root / f"{project_id}.json"

    def prepare(self, record: ProjectRecord) -> None:
        path = self._path(record.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            previous = ProjectRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if previous.owner_id != record.owner_id:
                raise PermissionError("project does not belong to the signed-in user")
            record = record.model_copy(update={"created_at": previous.created_at})
        path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def read_owned(self, project_id: str, owner_id: str) -> ProjectRecord:
        path = self._path(project_id)
        if not path.exists():
            raise FileNotFoundError(project_id)
        record = ProjectRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if record.owner_id != owner_id:
            raise PermissionError("project does not belong to the signed-in user")
        return record

    def list_owned(self, owner_id: str) -> list[ProjectRecord]:
        if not self.root.exists():
            return []
        records = [ProjectRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in self.root.glob("*.json")]
        return sorted((item for item in records if item.owner_id == owner_id), key=lambda item: item.updated_at, reverse=True)

    def update_checkpoint(self, run: RunRecord, checkpoint_sha256: str) -> ProjectRecord:
        if not run.project_id or not run.owner_id:
            raise ValueError("run is not bound to an owner project")
        previous = self.read_owned(run.project_id, run.owner_id)
        updated = previous.model_copy(update={
            "latest_run_id": run.run_id,
            "latest_status": run.status,
            "latest_checkpoint_sha256": checkpoint_sha256,
            "latest_receipt_ids": run.completed_receipt_ids,
            "updated_at": utc_now(),
        })
        self.prepare(updated)
        return updated


class CloudProjectStore:
    def __init__(self, *, project: str | None = None):
        self.project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.firestore = firestore.Client(project=self.project)

    def _doc(self, project_id: str):
        return self.firestore.collection("khalinos_projects").document(project_id)

    def prepare(self, record: ProjectRecord) -> None:
        snapshot = self._doc(record.project_id).get()
        if snapshot.exists:
            previous = ProjectRecord.model_validate(snapshot.to_dict())
            if previous.owner_id != record.owner_id:
                raise PermissionError("project does not belong to the signed-in user")
            record = record.model_copy(update={"created_at": previous.created_at})
        self._doc(record.project_id).set(record.model_dump(mode="json"))

    def read_owned(self, project_id: str, owner_id: str) -> ProjectRecord:
        snapshot = self._doc(project_id).get()
        if not snapshot.exists:
            raise FileNotFoundError(project_id)
        record = ProjectRecord.model_validate(snapshot.to_dict())
        if record.owner_id != owner_id:
            raise PermissionError("project does not belong to the signed-in user")
        return record

    def list_owned(self, owner_id: str) -> list[ProjectRecord]:
        snapshots = self.firestore.collection("khalinos_projects").where("owner_id", "==", owner_id).stream()
        records = [ProjectRecord.model_validate(item.to_dict()) for item in snapshots]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def update_checkpoint(self, run: RunRecord, checkpoint_sha256: str) -> ProjectRecord:
        if not run.project_id or not run.owner_id:
            raise ValueError("run is not bound to an owner project")
        previous = self.read_owned(run.project_id, run.owner_id)
        updated = previous.model_copy(update={
            "latest_run_id": run.run_id,
            "latest_status": RunStatus.PASSED,
            "latest_checkpoint_sha256": checkpoint_sha256,
            "latest_receipt_ids": run.completed_receipt_ids,
            "updated_at": utc_now(),
        })
        self.prepare(updated)
        return updated
