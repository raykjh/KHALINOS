"""Persistent SixSense intake state and user-supplied source material."""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.cloud import firestore, storage

from khalinos.models import IntakeRecord, SourceReference, utc_now


class LocalIntakeStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _intake(self, intake_id: str) -> Path:
        return self.root / "intakes" / intake_id

    def create(self, record: IntakeRecord, sources: list[tuple[SourceReference, bytes]]) -> None:
        root = self._intake(record.intake_id)
        root.mkdir(parents=True, exist_ok=False)
        for reference, data in sources:
            (root / "sources").mkdir(exist_ok=True)
            (root / "sources" / reference.source_id).write_bytes(data)
        self.update(record)

    def read(self, intake_id: str) -> IntakeRecord:
        target = self._intake(intake_id) / "record.json"
        if not target.exists():
            raise FileNotFoundError(intake_id)
        return IntakeRecord.model_validate_json(target.read_text(encoding="utf-8"))

    def update(self, record: IntakeRecord) -> None:
        record = record.model_copy(update={"updated_at": utc_now()})
        target = self._intake(record.intake_id) / "record.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def source_bytes(self, intake_id: str, reference: SourceReference) -> bytes:
        return (self._intake(intake_id) / "sources" / reference.source_id).read_bytes()


class CloudIntakeStore:
    def __init__(self, *, project: str | None = None, bucket: str | None = None):
        self.project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.bucket_name = bucket or os.environ["KHALINOS_BUCKET"]
        self.firestore = firestore.Client(project=self.project)
        self.bucket = storage.Client(project=self.project).bucket(self.bucket_name)

    def _doc(self, intake_id: str):
        return self.firestore.collection("khalinos_intakes").document(intake_id)

    def _source_blob(self, intake_id: str, reference: SourceReference):
        return self.bucket.blob(f"intakes/{intake_id}/sources/{reference.source_id}/{reference.filename}")

    def create(self, record: IntakeRecord, sources: list[tuple[SourceReference, bytes]]) -> None:
        for reference, data in sources:
            self._source_blob(record.intake_id, reference).upload_from_string(
                data,
                content_type=reference.media_type,
                if_generation_match=0,
            )
        self._doc(record.intake_id).create(record.model_dump(mode="json"))

    def read(self, intake_id: str) -> IntakeRecord:
        snapshot = self._doc(intake_id).get()
        if not snapshot.exists:
            raise FileNotFoundError(intake_id)
        return IntakeRecord.model_validate(snapshot.to_dict())

    def update(self, record: IntakeRecord) -> None:
        record = record.model_copy(update={"updated_at": utc_now()})
        self._doc(record.intake_id).set(record.model_dump(mode="json"))

    def source_bytes(self, intake_id: str, reference: SourceReference) -> bytes:
        return self._source_blob(intake_id, reference).download_as_bytes()


def intake_snapshot(record: IntakeRecord) -> str:
    """Stable text representation supplied to the sensing agent."""
    return json.dumps(record.model_dump(mode="json", exclude={"preview"}), ensure_ascii=False, indent=2)
