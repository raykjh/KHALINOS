"""Owner-bound resumable ZIP intake with deterministic archive admission."""

from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

from khalinos.models import (
    ArchiveSnapshot,
    ArtifactBundle,
    ArtifactFile,
    MaterialDescriptor,
    UploadCreate,
    UploadRecord,
    utc_now,
)


REQUIRED_BROWSER_FILES = ("index.html", "styles.css", "app.js", "journey.json", "README.md")
MAX_UNCOMPRESSED_BYTES = 25_000_000
MAX_COMPRESSION_RATIO = 100


def _safe_zip_name(name: str) -> PurePosixPath:
    if "\\" in name:
        raise ValueError("ZIP entries must use forward-slash relative paths")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("ZIP contains an unsafe path")
    if ":" in path.parts[0]:
        raise ValueError("ZIP contains an unsafe drive-qualified path")
    return path


def inspect_browser_zip(path: Path, *, bucket: str, object_name: str, generation: int) -> ArchiveSnapshot:
    """Admit only the bounded five-file browser profile; never extract during admission."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if size <= 0 or size > 200_000_000:
        raise ValueError("ZIP size is outside the approved 1 byte to 200 MB range")

    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError("uploaded object is not a valid ZIP archive") from exc
    with archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) != 5:
            raise ValueError("existing-project repair currently accepts exactly five browser source files")
        normalized: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        uncompressed = 0
        for member in members:
            entry = _safe_zip_name(member.filename)
            if member.flag_bits & 0x1:
                raise ValueError("encrypted ZIP entries are not accepted")
            unix_mode = (member.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                raise ValueError("symbolic links are not accepted in project ZIPs")
            if member.file_size <= 0 or member.file_size > 50_000:
                raise ValueError(f"source file is outside the 1 byte to 50 KB bound: {entry.name}")
            compressed = max(member.compress_size, 1)
            if member.file_size / compressed > MAX_COMPRESSION_RATIO:
                raise ValueError("ZIP compression ratio exceeds the approved safety bound")
            uncompressed += member.file_size
            normalized.append((member, entry))
        if uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("ZIP uncompressed size exceeds the approved safety bound")

        parent_sets = {entry.parts[:-1] for _, entry in normalized}
        if len(parent_sets) != 1:
            raise ValueError("the five browser files must share one archive directory")
        parent = next(iter(parent_sets))
        names = {entry.name for _, entry in normalized}
        if names != set(REQUIRED_BROWSER_FILES):
            raise ValueError("ZIP must contain index.html, styles.css, app.js, journey.json, and README.md")
        root_prefix = "/".join(parent)
        materials = [
            MaterialDescriptor(
                filename=entry.name,
                relative_path=entry.as_posix(),
                media_type={
                    ".html": "text/html",
                    ".css": "text/css",
                    ".js": "text/javascript",
                    ".json": "application/json",
                    ".md": "text/markdown",
                }[Path(entry.name).suffix.lower()],
                size_bytes=member.file_size,
            )
            for member, entry in sorted(normalized, key=lambda pair: pair[1].name)
        ]
    return ArchiveSnapshot(
        bucket=bucket,
        object_name=object_name,
        generation=generation,
        sha256=digest.hexdigest(),
        size_bytes=size,
        root_prefix=root_prefix,
        entry_count=len(members),
        uncompressed_size_bytes=uncompressed,
        materials=materials,
    )


def bundle_from_browser_zip(path: Path, snapshot: ArchiveSnapshot) -> ArtifactBundle:
    expected_prefix = f"{snapshot.root_prefix}/" if snapshot.root_prefix else ""
    files: list[ArtifactFile] = []
    with zipfile.ZipFile(path) as archive:
        for name in REQUIRED_BROWSER_FILES:
            member_name = expected_prefix + name
            try:
                raw = archive.read(member_name)
            except KeyError as exc:
                raise ValueError(f"validated source file is missing: {name}") from exc
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"browser source must be UTF-8 text: {name}") from exc
            files.append(ArtifactFile(path=name, content=content))
    return ArtifactBundle(revision_summary="Validated existing-project source snapshot", files=files)


class CloudUploadStore:
    def __init__(self, *, project: str | None = None, bucket: str | None = None):
        self.project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.bucket_name = bucket or os.environ["KHALINOS_BUCKET"]
        self.firestore = firestore.Client(project=self.project)
        self.bucket = storage.Client(project=self.project).bucket(self.bucket_name)

    def _doc(self, upload_id: str):
        return self.firestore.collection("khalinos_uploads").document(upload_id)

    def create_session(self, request: UploadCreate, owner_id: str) -> tuple[UploadRecord, str]:
        owned = self.firestore.collection("khalinos_uploads").where(
            filter=FieldFilter("owner_id", "==", owner_id)
        ).stream()
        if sum(1 for item in owned if item.to_dict().get("status") == "pending") >= 5:
            raise ValueError("at most five unfinished upload sessions are allowed per owner")
        upload_id = uuid4().hex
        owner_key = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:24]
        object_name = f"uploads/{owner_key}/{upload_id}/source.zip"
        blob = self.bucket.blob(object_name)
        blob.metadata = {"khalinos-upload-id": upload_id, "khalinos-owner-key": owner_key}
        origin = os.environ.get("KHALINOS_PUBLIC_ORIGIN", "").strip() or None
        session_uri = blob.create_resumable_upload_session(
            size=request.size_bytes,
            content_type="application/zip",
            origin=origin,
        )
        record = UploadRecord(
            upload_id=upload_id,
            owner_id=owner_id,
            filename=request.filename,
            expected_size_bytes=request.size_bytes,
            object_name=object_name,
        )
        self._doc(upload_id).create(record.model_dump(mode="json"))
        return record, session_uri

    def read_owned(self, upload_id: str, owner_id: str) -> UploadRecord:
        snapshot = self._doc(upload_id).get()
        if not snapshot.exists:
            raise FileNotFoundError(upload_id)
        record = UploadRecord.model_validate(snapshot.to_dict())
        if record.owner_id != owner_id:
            raise PermissionError("upload does not belong to the signed-in user")
        return record

    def finalize(self, upload_id: str, owner_id: str) -> UploadRecord:
        record = self.read_owned(upload_id, owner_id)
        if record.status == "finalized":
            return record
        if record.status == "rejected":
            raise ValueError(record.rejection_reason or "upload was rejected")
        blob = self.bucket.blob(record.object_name)
        try:
            blob.reload()
            owner_key = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:24]
            metadata = blob.metadata or {}
            if metadata.get("khalinos-upload-id") != upload_id or metadata.get("khalinos-owner-key") != owner_key:
                raise ValueError("uploaded object metadata does not match the authorized owner session")
            if blob.size != record.expected_size_bytes:
                raise ValueError("uploaded ZIP size does not match the authorized upload session")
            if blob.content_type not in {"application/zip", "application/octet-stream"}:
                raise ValueError("uploaded object is not a ZIP content type")
            with tempfile.TemporaryDirectory(prefix=f"khalinos-upload-{upload_id}-") as temporary:
                archive_path = Path(temporary) / "source.zip"
                blob.download_to_filename(archive_path, if_generation_match=blob.generation)
                admitted = inspect_browser_zip(
                    archive_path,
                    bucket=self.bucket_name,
                    object_name=record.object_name,
                    generation=int(blob.generation),
                )
            record = record.model_copy(update={"status": "finalized", "snapshot": admitted, "updated_at": utc_now()})
            self._doc(upload_id).set(record.model_dump(mode="json"))
            return record
        except Exception as exc:
            rejected = record.model_copy(update={
                "status": "rejected",
                "rejection_reason": f"{type(exc).__name__}: {exc}"[:500],
                "updated_at": utc_now(),
            })
            self._doc(upload_id).set(rejected.model_dump(mode="json"))
            raise

    def finalized_snapshot(self, upload_id: str, owner_id: str) -> ArchiveSnapshot:
        record = self.read_owned(upload_id, owner_id)
        if record.status != "finalized" or record.snapshot is None:
            raise ValueError("upload must be finalized before SixSense begins")
        return record.snapshot
