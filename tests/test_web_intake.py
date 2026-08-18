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
    assert "New project" in html
    assert "Improve an existing project" in html
    assert "Load Judge Demo inputs" in html
    assert "Choose from Project Library" in html
    assert "External project ZIP" in html


def test_intake_ui_explains_static_detection_and_executable_limit() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert "files are not executed at this stage" in html
    assert "material_inspection" in html
    assert "Sign in with Google" in html
    assert "sessionStorage" in html
    assert "function requireSignIn()" in html
    assert not re.search(r"[가-힣]", html)


def test_cloud_execution_uses_truthful_structured_camp_status() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert "Approved estimate" in html
    assert "Gemini calls" in html
    assert 'id="agentCamp"' in html
    assert 'id="handoffHorse"' in html
    assert "🐎" in html
    assert "Project Owner" in html
    assert "Technical Repair" in html
    assert "Independent Verifier" in html
    assert "function renderRun(record)" in html
    assert "record.message" in html
    assert "actual cost" not in html.lower()


def test_project_mode_can_switch_cleanly_before_goal_entry() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert 'id="startNewProject"' in html
    assert 'id="improveExisting"' in html
    assert "function clearWorkingMaterial()" in html
    assert "chooseWork('new')" in html
    assert "chooseWork('existing')" in html
    assert "Outcome discovery · autonomous execution" not in html
    assert "SixSense resolves what matters" not in html
