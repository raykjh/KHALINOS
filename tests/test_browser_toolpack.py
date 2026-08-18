from __future__ import annotations

import json
from pathlib import Path

import pytest

from khalinos.browser_toolpack import BROWSER_PRODUCT_MANIFEST, BROWSER_PRODUCT_TOOLPACK
from khalinos.models import ArtifactBundle, ArtifactFile


def browser_bundle() -> ArtifactBundle:
    values = {
        "index.html": "<!doctype html><button aria-label='Go'>Go</button>",
        "styles.css": "button{color:white}@media(max-width:600px){button{width:100%}}",
        "app.js": "document.querySelector('button').onclick=()=>{};",
        "journey.json": json.dumps({"journeys": [{"name": "go", "steps": [{"click": "button"}]}]}),
        "README.md": "# Product\n\nRun it locally.",
    }
    return ArtifactBundle(
        revision_summary="A complete browser fixture",
        files=[ArtifactFile(path=path, content=content) for path, content in values.items()],
    )


def test_browser_output_surface_is_owned_by_the_manifest(tmp_path: Path) -> None:
    artifact = browser_bundle()
    root = tmp_path / "product"

    BROWSER_PRODUCT_TOOLPACK.execution_adapter.materialize(artifact, root)

    assert sorted(path.name for path in root.iterdir()) == list(BROWSER_PRODUCT_MANIFEST.output.authorized_paths)


def test_browser_adapter_rejects_a_generic_but_unauthorized_artifact(tmp_path: Path) -> None:
    artifact = ArtifactBundle(
        revision_summary="A safe generic artifact outside this pack",
        files=[ArtifactFile(path="artifact.txt", content="safe text")],
    )

    with pytest.raises(PermissionError, match="output contract"):
        BROWSER_PRODUCT_TOOLPACK.execution_adapter.materialize(artifact, tmp_path / "product")
    assert not (tmp_path / "product").exists()
