from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from khalinos.uploads import REQUIRED_BROWSER_FILES, bundle_from_browser_zip, inspect_browser_zip


def write_zip(path: Path, names: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in names.items():
            archive.writestr(name, content)


def valid_files(prefix: str = "") -> dict[str, str]:
    values = {
        "index.html": "<!doctype html><button aria-label='Move'>Move</button>",
        "styles.css": "@media(max-width:600px){button{width:100%}}",
        "app.js": "document.querySelector('button').onclick=()=>{};",
        "journey.json": '{"journeys":[{"name":"move","steps":[{"click":"button"}]}]}',
        "README.md": "# Existing project\n",
    }
    return {prefix + name: content for name, content in values.items()}


def test_valid_browser_zip_is_digest_bound_without_extraction(tmp_path: Path) -> None:
    archive = tmp_path / "project.zip"
    write_zip(archive, valid_files("project/"))
    snapshot = inspect_browser_zip(archive, bucket="bucket", object_name="uploads/a/source.zip", generation=7)
    bundle = bundle_from_browser_zip(archive, snapshot)
    assert snapshot.root_prefix == "project"
    assert snapshot.entry_count == 5
    assert {item.path for item in bundle.files} == set(REQUIRED_BROWSER_FILES)


def test_zip_rejects_path_traversal_and_extra_files(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    values = valid_files()
    values["../secret.txt"] = "secret"
    write_zip(archive, values)
    with pytest.raises(ValueError, match="unsafe path"):
        inspect_browser_zip(archive, bucket="bucket", object_name="uploads/a/source.zip", generation=1)


def test_zip_rejects_non_browser_project_profile(tmp_path: Path) -> None:
    archive = tmp_path / "godot.zip"
    write_zip(archive, {"project.godot": "[application]"})
    with pytest.raises(ValueError, match="five browser source files"):
        inspect_browser_zip(archive, bucket="bucket", object_name="uploads/a/source.zip", generation=1)
