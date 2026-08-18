"""The approved browser-product ToolPack shipped with this KHALINOS release."""

from __future__ import annotations

from pathlib import Path

from khalinos.models import ArtifactBundle, DeterministicEvidence
from khalinos.toolpacks import (
    CapabilityDeclaration,
    EvidenceContract,
    OutputContract,
    RegisteredToolPack,
    ToolPackManifest,
)
from khalinos.verification import materialize, verify_bundle


class BrowserExecutionAdapter:
    adapter_id = "browser.static.execution.v1"

    def materialize(self, artifact: ArtifactBundle, root: Path) -> None:
        materialize(artifact, root)


class BrowserEvidenceAdapter:
    adapter_id = "browser.chromium.evidence.v1"

    def verify(
        self,
        artifact: ArtifactBundle,
        root: Path,
        evidence_dir: Path,
        acceptance_criteria: list[str],
    ) -> DeterministicEvidence:
        return verify_bundle(artifact, root, evidence_dir, acceptance_criteria)


BROWSER_PRODUCT_MANIFEST = ToolPackManifest(
    toolpack_id="browser.product",
    version="1.0.0",
    display_name="Browser Product ToolPack",
    description="Builds, repairs, runs, and verifies bounded offline browser micro-products.",
    execution_adapter_id=BrowserExecutionAdapter.adapter_id,
    project_kinds=("browser", "web"),
    work_modes=("existing_project_repair", "new_product_build"),
    capabilities=(
        CapabilityDeclaration(
            capability_id="browser.artifact.control",
            operations=("build", "repair"),
            scopes=("artifact:read", "artifact:write"),
        ),
        CapabilityDeclaration(
            capability_id="browser.runtime.evidence",
            operations=("execute", "observe"),
            scopes=("loopback:http", "runtime:headless"),
        ),
    ),
    output=OutputContract(
        artifact_kind="browser.five-file-bundle",
        authorized_paths=("README.md", "app.js", "index.html", "journey.json", "styles.css"),
        max_file_count=5,
        max_total_bytes=150_000,
    ),
    evidence=EvidenceContract(
        adapter_id=BrowserEvidenceAdapter.adapter_id,
        evidence_types=("chromium.journey", "runtime.assertion", "runtime.screenshot"),
        network_isolated=True,
        independent_verifier_required=True,
    ),
)


BROWSER_PRODUCT_TOOLPACK = RegisteredToolPack[
    ArtifactBundle, DeterministicEvidence
](
    manifest=BROWSER_PRODUCT_MANIFEST,
    execution_adapter=BrowserExecutionAdapter(),
    evidence_adapter=BrowserEvidenceAdapter(),
)
