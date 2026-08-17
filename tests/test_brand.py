from __future__ import annotations

from pathlib import Path


def test_submission_tree_contains_only_khalinos_brand() -> None:
    root = Path(__file__).parents[1]
    forbidden = "one" + "brief"
    offenders = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        if forbidden in path.name.casefold():
            offenders.append(str(path.relative_to(root)))
            continue
        try:
            if forbidden in path.read_text(encoding="utf-8").casefold():
                offenders.append(str(path.relative_to(root)))
        except UnicodeDecodeError:
            pass
    assert offenders == []

