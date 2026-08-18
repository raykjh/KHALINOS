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


def test_goal_has_no_leading_example_and_sixsense_requires_a_real_choice() -> None:
    html = WEB.read_text(encoding="utf-8")
    goal = re.search(r'<textarea id="goal"[^>]*>', html)
    assert goal is not None
    assert "Describe what you want to create in detail" in goal.group(0)
    assert "WASD" not in goal.group(0)
    assert 'id="answerOptions"' in html
    assert "question.answer_options" in html
    assert "Confirm this choice" in html
    assert "SixSense asks no more than six questions" in html
    assert "questionKicker" not in html
    assert 'id="userChoices"' in html
    assert "KHALINOS applied professional defaults" in html
    assert "$('#answer').value=question.recommended_answer" not in html


def test_execution_camp_shows_branching_verification_and_repair_loop() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert 'class="flow-lines"' in html
    assert 'data-role="runtime"' in html
    assert "Runtime Check" in html
    assert "EXISTING PROJECT" in html
    assert "REPAIR" in html
    assert "runtime_checking:'runtime'" in html


def test_passed_project_can_be_opened_from_result_and_library() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert "Play verified result" in html
    assert "Play result" in html
    assert "/artifact`" in html
    assert "function playProject(projectId)" in html
    assert "DOMParser" in html
