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
from typing import Generic, Iterable, Literal, Protocol, TypeVar

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


class RoutingContract(BaseModel):
    """Human- and model-readable scope used before authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_project_kind: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    supported_outcomes: tuple[str, ...] = Field(min_length=1, max_length=16)
    excluded_outcomes: tuple[str, ...] = Field(default=(), max_length=16)
    selection_guidance: str = Field(min_length=20, max_length=500)

    @model_validator(mode="after")
    def canonical_outcomes(self) -> "RoutingContract":
        for label, values in (
            ("supported outcomes", self.supported_outcomes),
            ("excluded outcomes", self.excluded_outcomes),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"routing {label} must be unique and sorted")
        return self


class ExternalDependency(BaseModel):
    """One exact non-source dependency admitted into a ToolPack boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dependency_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,63}$")
    kind: Literal["executable", "model", "package"]
    version: str = Field(min_length=1, max_length=80)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(ge=1, le=5_000_000_000)
    source_url: str = Field(pattern=r"^https://", max_length=500)
    license_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.+-]{1,63}$")


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
    external_dependencies: tuple[ExternalDependency, ...] = Field(default=(), max_length=32)
    routing: RoutingContract
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
        dependency_ids = tuple(item.dependency_id for item in self.external_dependencies)
        if tuple(sorted(set(dependency_ids))) != dependency_ids:
            raise ValueError("ToolPack dependencies must be unique and sorted by dependency_id")
        if self.routing.primary_project_kind not in self.project_kinds:
            raise ValueError("routing primary_project_kind must be declared by the ToolPack")
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

    def select(
        self,
        *,
        project_kind: str,
        work_mode: str,
        requested_toolpack_id: str | None = None,
    ) -> RegisteredToolPack:
        """Select one compatible approved ToolPack without a default fallback."""

        if requested_toolpack_id is not None:
            try:
                candidates = [self._toolpacks[requested_toolpack_id]]
            except KeyError as exc:
                raise PermissionError(
                    f"ToolPack is not approved: {requested_toolpack_id}"
                ) from exc
        else:
            candidates = list(self._toolpacks.values())
        compatible = [
            toolpack
            for toolpack in candidates
            if project_kind in toolpack.manifest.project_kinds
            and work_mode in toolpack.manifest.work_modes
        ]
        if not compatible:
            requested = f" requested={requested_toolpack_id}" if requested_toolpack_id else ""
            raise PermissionError(
                "No approved ToolPack matches "
                f"project_kind={project_kind} work_mode={work_mode}{requested}"
            )
        if len(compatible) != 1:
            identifiers = sorted(item.manifest.toolpack_id for item in compatible)
            raise PermissionError(
                "ToolPack selection is ambiguous; an explicit approved ToolPack is required: "
                + ", ".join(identifiers)
            )
        return compatible[0]

    def manifest_snapshots(self) -> tuple[ToolPackManifest, ...]:
        return tuple(self._toolpacks[key].manifest for key in sorted(self._toolpacks))

    def routing_candidates(self, *, work_mode: str) -> tuple[ToolPackManifest, ...]:
        """Return approved manifests compatible with a work mode, without selecting one."""

        return tuple(
            toolpack.manifest
            for key, toolpack in sorted(self._toolpacks.items())
            if work_mode in toolpack.manifest.work_modes
        )
