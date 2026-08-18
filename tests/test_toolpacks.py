from __future__ import annotations

from pathlib import Path

import pytest

from khalinos.toolpacks import (
    CapabilityDeclaration,
    EvidenceContract,
    OutputContract,
    RegisteredToolPack,
    ToolPackBinding,
    ToolPackManifest,
    ToolPackRegistry,
    source_set_sha256,
)


class FakeExecutionAdapter:
    adapter_id = "fixture.execution.v1"

    def materialize(self, artifact: object, root: Path) -> None:
        del artifact, root


class FakeEvidenceAdapter:
    adapter_id = "fixture.evidence.v1"

    def verify(
        self,
        artifact: object,
        root: Path,
        evidence_dir: Path,
        acceptance_criteria: list[str],
    ) -> dict:
        del artifact, root, evidence_dir, acceptance_criteria
        return {"passed": True}


def manifest() -> ToolPackManifest:
    return ToolPackManifest(
        toolpack_id="fixture.product",
        version="1.0.0",
        display_name="Fixture Product",
        description="A domain-neutral fixture used to test Kernel contracts.",
        implementation_sha256="1" * 64,
        execution_adapter_id="fixture.execution.v1",
        project_kinds=("fixture",),
        work_modes=("build", "repair"),
        capabilities=(
            CapabilityDeclaration(
                capability_id="fixture.control",
                operations=("build", "repair"),
                scopes=("artifact:read", "artifact:write"),
            ),
        ),
        output=OutputContract(
            artifact_kind="fixture.bundle",
            authorized_paths=("artifact.txt",),
            max_file_count=1,
            max_total_bytes=1024,
        ),
        evidence=EvidenceContract(
            adapter_id="fixture.evidence.v1",
            evidence_types=("deterministic.fixture",),
        ),
    )


def registered() -> RegisteredToolPack:
    return RegisteredToolPack(manifest(), FakeExecutionAdapter(), FakeEvidenceAdapter())


def test_manifest_digest_is_canonical_and_binding_is_exact() -> None:
    first = registered()
    second = registered()
    assert first.manifest.sha256() == second.manifest.sha256()
    assert first.binding() == second.binding()


def test_registry_resolves_only_the_exact_approved_binding() -> None:
    pack = registered()
    registry = ToolPackRegistry([pack])
    assert registry.resolve(pack.binding()) is pack

    changed = ToolPackBinding(
        toolpack_id=pack.binding().toolpack_id,
        version=pack.binding().version,
        manifest_sha256="0" * 64,
    )
    with pytest.raises(PermissionError, match="does not match"):
        registry.resolve(changed)
    with pytest.raises(PermissionError, match="not approved"):
        registry.binding_for("unknown.product")


def test_registry_and_adapter_contracts_reject_ambiguous_registration() -> None:
    pack = registered()
    with pytest.raises(ValueError, match="duplicate"):
        ToolPackRegistry([pack, pack])

    class WrongExecutionAdapter(FakeExecutionAdapter):
        adapter_id = "wrong.execution.v1"

    with pytest.raises(ValueError, match="execution adapter"):
        RegisteredToolPack(manifest(), WrongExecutionAdapter(), FakeEvidenceAdapter())


def test_manifest_collections_and_paths_are_canonical_and_bounded() -> None:
    raw = manifest().model_dump(mode="json")
    raw["work_modes"] = ["repair", "build"]
    with pytest.raises(ValueError, match="unique and sorted"):
        ToolPackManifest.model_validate(raw)

    raw = manifest().model_dump(mode="json")
    raw["output"]["authorized_paths"] = ["../outside.txt"]
    with pytest.raises(ValueError, match="artifact root"):
        ToolPackManifest.model_validate(raw)


def test_implementation_source_digest_is_newline_neutral_and_change_sensitive(tmp_path: Path) -> None:
    source = tmp_path / "adapter.py"
    source.write_bytes(b"first\nsecond\n")
    first = source_set_sha256(tmp_path, ["adapter.py"])
    source.write_bytes(b"first\r\nsecond\r\n")
    assert source_set_sha256(tmp_path, ["adapter.py"]) == first
    source.write_bytes(b"first\nchanged\n")
    assert source_set_sha256(tmp_path, ["adapter.py"]) != first
