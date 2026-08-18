from __future__ import annotations

import re
from pathlib import Path


WEB = Path(__file__).parents[1] / "src" / "khalinos" / "web" / "index.html"


def test_materials_precede_goal_and_sixsense() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert html.index('id="materialsStep"') < html.index('id="goalStep"') < html.index('id="sensesStep"')
    assert "What should KHALINOS work from?" in html
    assert "What should change or exist when this is finished?" in html
    assert "/api/materials/inspect" in html
    assert "Try Judge Demo" in html
    assert "Choose a KHALINOS project" in html
    assert "External project ZIP" in html


def test_intake_ui_explains_static_detection_and_executable_limit() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert "files are not executed at this stage" in html
    assert "material_inspection" in html
    assert "Sign in with Google" in html
    assert not re.search(r"[가-힣]", html)
