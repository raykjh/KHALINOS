"""Domain-neutral, approval-bound ToolPack contracts for the KHALINOS Kernel.

This module deliberately contains no browser, game-engine, or document-specific
branching.  A ToolPack supplies those details behind execution and evidence
adapters; the Kernel only resolves an exact approved manifest digest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Iterable, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


ArtifactT = TypeVar("ArtifactT")
EvidenceT = TypeVar("EvidenceT")


def source_set_sha256(root: Path, relative_paths: Iterable[str]) -> str:
    """Hash a declared implementation source set with platform-neutral newlines."""

    digest = hashlib.sha256()
    for relative in sorted(set(relative_paths)):
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"ToolPack implementation source is missing: {relative}")
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


class CapabilityDeclaration(BaseModel):
    """One bounded ability exposed by a ToolPack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    operations: tuple[str, ...] = Field(min_length=1, max_length=32)
    scopes: tuple[str, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def canonical_sets(self) -> "CapabilityDeclaration":
        if tuple(sorted(set(self.operations))) != self.operations:
            raise ValueError("capability operations must be unique and sorted")
        if tuple(sorted(set(self.scopes))) != self.scopes:
            raise ValueError("capability scopes must be unique and sorted")
        return self


class OutputContract(BaseModel):
    """Bounded artifact surface owned by the ToolPack, not by the Kernel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_kind: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    authorized_paths: tuple[str, ...] = Field(min_length=1, max_length=256)
    max_file_count: int = Field(ge=1, le=10_000)
    max_total_bytes: int = Field(ge=1, le=5_000_000_000)

    @model_validator(mode="after")
    def canonical_paths(self) -> "OutputContract":
        if tuple(sorted(set(self.authorized_paths))) != self.authorized_paths:
            raise ValueError("authorized output paths must be unique and sorted")
        if len(self.authorized_paths) > self.max_file_count:
            raise ValueError("authorized output paths exceed max_file_count")
        if any(path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/") for path in self.authorized_paths):
            raise ValueError("authorized output paths must stay relative to the artifact root")
        return self


class EvidenceContract(BaseModel):
    """Verifier boundary that a ToolPack promises to satisfy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    evidence_types: tuple[str, ...] = Field(min_length=1, max_length=32)
    network_isolated: bool = True
    independent_verifier_required: bool = True

    @model_validator(mode="after")
    def canonical_evidence_types(self) -> "EvidenceContract":
        if tuple(sorted(set(self.evidence_types))) != self.evidence_types:
            raise ValueError("evidence types must be unique and sorted")
        return self


class ToolPackManifest(BaseModel):
    """Immutable description of one statically approved set of hands and senses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    toolpack_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    display_name: str = Field(min_length=3, max_length=80)
    description: str = Field(min_length=20, max_length=500)
    implementation_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    execution_adapter_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    project_kinds: tuple[str, ...] = Field(min_length=1, max_length=32)
    work_modes: tuple[str, ...] = Field(min_length=1, max_length=32)
    capabilities: tuple[CapabilityDeclaration, ...] = Field(min_length=1, max_length=32)
    output: OutputContract
    evidence: EvidenceContract

    @model_validator(mode="after")
    def canonical_collections(self) -> "ToolPackManifest":
        for label, values in (
            ("project kinds", self.project_kinds),
            ("work modes", self.work_modes),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"ToolPack {label} must be unique and sorted")
        capability_ids = tuple(item.capability_id for item in self.capabilities)
        if tuple(sorted(set(capability_ids))) != capability_ids:
            raise ValueError("ToolPack capabilities must be unique and sorted by capability_id")
        return self

    def sha256(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ToolPackBinding(BaseModel):
    """The exact ToolPack revision sealed into an authorization contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    toolpack_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ExecutionAdapter(Protocol[ArtifactT]):
    """Materializes an artifact without issuing Quests or expanding authority."""

    adapter_id: str

    def materialize(self, artifact: ArtifactT, root: Path) -> None: ...


class EvidenceAdapter(Protocol[ArtifactT, EvidenceT]):
    """Produces deterministic evidence without deciding final completion."""

    adapter_id: str

    def verify(
        self,
        artifact: ArtifactT,
        root: Path,
        evidence_dir: Path,
        acceptance_criteria: list[str],
    ) -> EvidenceT: ...


@dataclass(frozen=True)
class RegisteredToolPack(Generic[ArtifactT, EvidenceT]):
    manifest: ToolPackManifest
    execution_adapter: ExecutionAdapter[ArtifactT]
    evidence_adapter: EvidenceAdapter[ArtifactT, EvidenceT]

    def __post_init__(self) -> None:
        if self.execution_adapter.adapter_id != self.manifest.execution_adapter_id:
            raise ValueError("execution adapter does not match the ToolPack manifest")
        if self.evidence_adapter.adapter_id != self.manifest.evidence.adapter_id:
            raise ValueError("evidence adapter does not match the ToolPack manifest")

    def binding(self) -> ToolPackBinding:
        return ToolPackBinding(
            toolpack_id=self.manifest.toolpack_id,
            version=self.manifest.version,
            manifest_sha256=self.manifest.sha256(),
        )


class ToolPackRegistry:
    """Static allow-list that resolves only exact, digest-bound ToolPacks."""

    def __init__(self, toolpacks: Iterable[RegisteredToolPack] = ()) -> None:
        self._toolpacks: dict[str, RegisteredToolPack] = {}
        for toolpack in toolpacks:
            self.register(toolpack)

    def register(self, toolpack: RegisteredToolPack) -> None:
        key = toolpack.manifest.toolpack_id
        if key in self._toolpacks:
            raise ValueError(f"duplicate ToolPack id: {key}")
        self._toolpacks[key] = toolpack

    def binding_for(self, toolpack_id: str) -> ToolPackBinding:
        try:
            return self._toolpacks[toolpack_id].binding()
        except KeyError as exc:
            raise PermissionError(f"ToolPack is not approved: {toolpack_id}") from exc

    def resolve(self, binding: ToolPackBinding) -> RegisteredToolPack:
        try:
            toolpack = self._toolpacks[binding.toolpack_id]
        except KeyError as exc:
            raise PermissionError(f"ToolPack is not approved: {binding.toolpack_id}") from exc
        approved = toolpack.binding()
        if binding != approved:
            raise PermissionError("ToolPack binding does not match the approved manifest")
        return toolpack

    def manifest_snapshots(self) -> tuple[ToolPackManifest, ...]:
        return tuple(self._toolpacks[key].manifest for key in sorted(self._toolpacks))
