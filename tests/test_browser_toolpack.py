from __future__ import annotations

import json
from pathlib import Path

import pytest

from khalinos.browser_artifacts import BrowserArtifactBundle
from khalinos.browser_toolpack import (
    BROWSER_IMPLEMENTATION_SOURCES,
    BROWSER_PRODUCT_MANIFEST,
    BROWSER_PRODUCT_TOOLPACK,
)
from khalinos.models import ArtifactBundle, ArtifactFile
from khalinos.toolpacks import source_set_sha256


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

    assert sorted(path.name for path in root.iterdir()) == ["README.md", "app.js", "index.html", "journey.json", "styles.css"]


def test_browser_manifest_binds_the_actual_adapter_implementation() -> None:
    package_root = Path(__file__).parents[1] / "src" / "khalinos"
    assert BROWSER_PRODUCT_MANIFEST.implementation_sha256 == source_set_sha256(
        package_root,
        BROWSER_IMPLEMENTATION_SOURCES,
    )


def test_browser_adapter_rejects_a_generic_but_unauthorized_artifact(tmp_path: Path) -> None:
    artifact = ArtifactBundle(
        revision_summary="A safe generic artifact outside this pack",
        files=[ArtifactFile(path="artifact.txt", content="safe text")],
    )

    with pytest.raises(PermissionError, match="output contract"):
        BROWSER_PRODUCT_TOOLPACK.execution_adapter.materialize(artifact, tmp_path / "product")
    assert not (tmp_path / "product").exists()


def test_gemini_browser_schema_remains_strict_while_kernel_bundle_is_generic() -> None:
    generic = ArtifactBundle(
        revision_summary="A generic artifact accepted by the Kernel",
        files=[ArtifactFile(path="artifact.txt", content="safe text")],
    )
    assert generic.files[0].path == "artifact.txt"
    with pytest.raises(ValueError):
        BrowserArtifactBundle.model_validate(generic.model_dump(mode="json"))
    assert "assets" not in BrowserArtifactBundle.model_json_schema()["properties"]


def test_gemini_browser_schema_bounds_verbose_freeform_summary() -> None:
    values = browser_bundle().file_map()
    model_output = BrowserArtifactBundle.model_validate(
        {
            "revision_summary": "Summary prose. " * 100,
            "files": [{"path": path, "content": content} for path, content in values.items()],
        }
    )

    assert len(model_output.revision_summary) == 500


def test_trusted_promotion_removes_external_css_import_without_touching_product_css() -> None:
    values = browser_bundle().file_map()
    values["styles.css"] = (
        "@import url('https://fonts.googleapis.com/css2?family=Forum');\n"
        "button{font-family:Forum,serif;color:white}@media(max-width:600px){button{width:100%}}"
    )
    model_output = BrowserArtifactBundle.model_validate({
        "revision_summary": "A model browser output with a prohibited remote font import",
        "files": [{"path": path, "content": content} for path, content in values.items()],
    })
    promoted = model_output.to_artifact_bundle()
    assert "https://" not in promoted.file_map()["styles.css"]
    assert "button{font-family:Forum,serif" in promoted.file_map()["styles.css"]
    assert "Trusted host removed prohibited external CSS imports" in promoted.revision_summary
