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
    ArtifactAsset,
    ArtifactBundle,
    ArtifactFile,
    MaterialDescriptor,
    UploadCreate,
    UploadRecord,
    utc_now,
)
from khalinos.visual_assets import ASSET_PATH, trusted_png_asset


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
    """Admit the bounded browser profile plus its one optional trusted PNG asset."""
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
        if len(members) not in {5, 6}:
            raise ValueError("existing-project repair accepts five browser source files and one optional visual asset")
        normalized: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        uncompressed = 0
        for member in members:
            entry = _safe_zip_name(member.filename)
            if member.flag_bits & 0x1:
                raise ValueError("encrypted ZIP entries are not accepted")
            unix_mode = (member.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                raise ValueError("symbolic links are not accepted in project ZIPs")
            is_asset = entry.as_posix().endswith(ASSET_PATH)
            limit = 2_500_000 if is_asset else 50_000
            if member.file_size <= 0 or member.file_size > limit:
                raise ValueError(f"source file is outside its approved size bound: {entry.name}")
            compressed = max(member.compress_size, 1)
            if member.file_size / compressed > MAX_COMPRESSION_RATIO:
                raise ValueError("ZIP compression ratio exceeds the approved safety bound")
            uncompressed += member.file_size
            normalized.append((member, entry))
        if uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("ZIP uncompressed size exceeds the approved safety bound")

        text_entries = [(member, entry) for member, entry in normalized if entry.name in REQUIRED_BROWSER_FILES]
        if len(text_entries) != 5:
            raise ValueError("ZIP must contain index.html, styles.css, app.js, journey.json, and README.md")
        parent_sets = {entry.parts[:-1] for _, entry in text_entries}
        if len(parent_sets) != 1:
            raise ValueError("the five browser files must share one archive directory")
        parent = next(iter(parent_sets))
        names = {entry.name for _, entry in text_entries}
        if names != set(REQUIRED_BROWSER_FILES):
            raise ValueError("ZIP must contain index.html, styles.css, app.js, journey.json, and README.md")
        asset_entries = [(member, entry) for member, entry in normalized if entry.name not in REQUIRED_BROWSER_FILES]
        expected_asset = (*parent, "assets", "visual-foundation.png")
        if asset_entries and (len(asset_entries) != 1 or asset_entries[0][1].parts != expected_asset):
            raise ValueError("the only optional binary path is assets/visual-foundation.png")
        root_prefix = "/".join(parent)
        materials = [
            MaterialDescriptor(
                filename=entry.name,
                relative_path=entry.as_posix(),
                media_type=("image/png" if entry.name == "visual-foundation.png" else {
                    ".html": "text/html",
                    ".css": "text/css",
                    ".js": "text/javascript",
                    ".json": "application/json",
                    ".md": "text/markdown",
                }[Path(entry.name).suffix.lower()]),
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
    assets: list[ArtifactAsset] = []
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
        asset_member = expected_prefix + ASSET_PATH
        if asset_member in archive.namelist():
            assets.append(trusted_png_asset(archive.read(asset_member)))
    return ArtifactBundle(
        revision_summary="Validated existing-project source snapshot",
        files=files,
        assets=assets,
    )


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
