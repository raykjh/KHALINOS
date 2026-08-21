"""Cloud and local run stores with immutable evidence paths."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Protocol

from google.cloud import firestore, storage

from khalinos.models import ArchiveSnapshot, ArtifactBundle, RunRecord, RunStatus, UserBrief, utc_now
from khalinos.uploads import bundle_from_browser_zip, inspect_browser_zip


class RunStore(Protocol):
    def create(self, record: RunRecord, brief: UserBrief) -> None: ...
    def claim_execution(self, run_id: str) -> RunRecord | None: ...
    def read_brief(self, run_id: str) -> UserBrief: ...
    def read_record(self, run_id: str) -> RunRecord: ...
    def update(self, record: RunRecord) -> None: ...
    def put_json(self, run_id: str, relative: str, payload: dict | list) -> str: ...
    def put_file(self, run_id: str, relative: str, source: Path, content_type: str) -> str: ...
    def put_bytes(self, run_id: str, relative: str, payload: bytes, content_type: str) -> str: ...
    def put_bundle_archive(self, run_id: str, bundle: ArtifactBundle) -> ArchiveSnapshot: ...
    def read_bundle_archive(self, snapshot: ArchiveSnapshot) -> ArtifactBundle: ...


class LocalRunStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _run(self, run_id: str) -> Path:
        return self.root / "runs" / run_id

    def create(self, record: RunRecord, brief: UserBrief) -> None:
        root = self._run(record.run_id)
        root.mkdir(parents=True, exist_ok=False)
        (root / "brief.json").write_text(brief.model_dump_json(indent=2) + "\n", encoding="utf-8")
        self.update(record)

    def claim_execution(self, run_id: str) -> RunRecord | None:
        record = self.read_record(run_id)
        if record.status != RunStatus.QUEUED:
            return None
        claim = self._run(run_id) / ".execution-claim"
        try:
            with claim.open("x", encoding="utf-8") as handle:
                handle.write(run_id + "\n")
        except FileExistsError:
            return None
        claimed = record.model_copy(update={
            "status": RunStatus.PLANNING,
            "message": "One worker claimed the immutable run for execution.",
        })
        self.update(claimed)
        return claimed

    def read_brief(self, run_id: str) -> UserBrief:
        return UserBrief.model_validate_json((self._run(run_id) / "brief.json").read_text(encoding="utf-8"))

    def read_record(self, run_id: str) -> RunRecord:
        return RunRecord.model_validate_json((self._run(run_id) / "record.json").read_text(encoding="utf-8"))

    def update(self, record: RunRecord) -> None:
        record = record.model_copy(update={"updated_at": utc_now()})
        target = self._run(record.run_id) / "record.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def put_json(self, run_id: str, relative: str, payload: dict | list) -> str:
        target = self._run(run_id) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(target)

    def put_file(self, run_id: str, relative: str, source: Path, content_type: str) -> str:
        del content_type
        target = self._run(run_id) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return str(target)

    def put_bytes(self, run_id: str, relative: str, payload: bytes, content_type: str) -> str:
        del content_type
        target = self._run(run_id) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return str(target)

    def put_bundle_archive(self, run_id: str, bundle: ArtifactBundle) -> ArchiveSnapshot:
        target = self._run(run_id) / "final" / "source.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in bundle.files:
                archive.writestr(item.path, item.content.encode("utf-8"))
            for asset in bundle.assets:
                archive.writestr(asset.path, asset.bytes())
        return inspect_browser_zip(target, bucket="local", object_name=str(target), generation=1)

    def read_bundle_archive(self, snapshot: ArchiveSnapshot) -> ArtifactBundle:
        if snapshot.bucket != "local":
            raise ValueError("local run store cannot read a Cloud snapshot")
        return bundle_from_browser_zip(Path(snapshot.object_name), snapshot)


class CloudRunStore:
    def __init__(self, *, project: str | None = None, bucket: str | None = None):
        self.project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.bucket_name = bucket or os.environ["KHALINOS_BUCKET"]
        self.firestore = firestore.Client(project=self.project)
        self.bucket = storage.Client(project=self.project).bucket(self.bucket_name)

    def _doc(self, run_id: str):
        return self.firestore.collection("khalinos_runs").document(run_id)

    def _blob(self, run_id: str, relative: str):
        return self.bucket.blob(f"runs/{run_id}/{relative}")

    def create(self, record: RunRecord, brief: UserBrief) -> None:
        self._blob(record.run_id, "brief.json").upload_from_string(
            brief.model_dump_json(indent=2) + "\n",
            content_type="application/json",
            if_generation_match=0,
        )
        self._doc(record.run_id).create(record.model_dump(mode="json"))

    def claim_execution(self, run_id: str) -> RunRecord | None:
        document = self._doc(run_id)
        transaction = self.firestore.transaction()

        @firestore.transactional
        def claim(active_transaction):
            snapshot = document.get(transaction=active_transaction)
            if not snapshot.exists:
                raise FileNotFoundError(run_id)
            record = RunRecord.model_validate(snapshot.to_dict())
            if record.status != RunStatus.QUEUED:
                return None
            claimed = record.model_copy(update={
                "status": RunStatus.PLANNING,
                "message": "One worker claimed the immutable run for execution.",
                "updated_at": utc_now(),
            })
            active_transaction.set(document, claimed.model_dump(mode="json"))
            return claimed

        return claim(transaction)

    def read_brief(self, run_id: str) -> UserBrief:
        return UserBrief.model_validate_json(self._blob(run_id, "brief.json").download_as_text())

    def read_record(self, run_id: str) -> RunRecord:
        snapshot = self._doc(run_id).get()
        if not snapshot.exists:
            raise FileNotFoundError(run_id)
        return RunRecord.model_validate(snapshot.to_dict())

    def update(self, record: RunRecord) -> None:
        record = record.model_copy(update={"updated_at": utc_now()})
        self._doc(record.run_id).set(record.model_dump(mode="json"))

    def put_json(self, run_id: str, relative: str, payload: dict | list) -> str:
        blob = self._blob(run_id, relative)
        blob.upload_from_string(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            content_type="application/json",
        )
        return f"gs://{self.bucket_name}/{blob.name}"

    def put_file(self, run_id: str, relative: str, source: Path, content_type: str) -> str:
        blob = self._blob(run_id, relative)
        blob.upload_from_filename(str(source), content_type=content_type)
        return f"gs://{self.bucket_name}/{blob.name}"

    def put_bytes(self, run_id: str, relative: str, payload: bytes, content_type: str) -> str:
        blob = self._blob(run_id, relative)
        blob.upload_from_string(payload, content_type=content_type)
        return f"gs://{self.bucket_name}/{blob.name}"

    def put_bundle_archive(self, run_id: str, bundle: ArtifactBundle) -> ArchiveSnapshot:
        with tempfile.TemporaryDirectory(prefix=f"khalinos-final-{run_id}-") as temporary:
            target = Path(temporary) / "source.zip"
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for item in bundle.files:
                    archive.writestr(item.path, item.content.encode("utf-8"))
                for asset in bundle.assets:
                    archive.writestr(asset.path, asset.bytes())
            blob = self._blob(run_id, "final/source.zip")
            blob.upload_from_filename(str(target), content_type="application/zip")
            blob.reload()
            return inspect_browser_zip(
                target,
                bucket=self.bucket_name,
                object_name=blob.name,
                generation=int(blob.generation),
            )

    def read_bundle_archive(self, snapshot: ArchiveSnapshot) -> ArtifactBundle:
        if snapshot.bucket != self.bucket_name:
            raise PermissionError("source snapshot is outside the approved KHALINOS bucket")
        blob = self.bucket.blob(snapshot.object_name, generation=snapshot.generation)
        with tempfile.TemporaryDirectory(prefix="khalinos-source-") as temporary:
            target = Path(temporary) / "source.zip"
            blob.download_to_filename(target, if_generation_match=snapshot.generation)
            admitted = inspect_browser_zip(
                target,
                bucket=snapshot.bucket,
                object_name=snapshot.object_name,
                generation=snapshot.generation,
            )
            if admitted.sha256 != snapshot.sha256:
                raise ValueError("source archive digest no longer matches the approved snapshot")
            return bundle_from_browser_zip(target, snapshot)
