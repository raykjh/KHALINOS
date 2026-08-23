from __future__ import annotations

import re
from pathlib import Path


WEB = Path(__file__).parents[1] / "src" / "khalinos" / "web" / "index.html"


def test_materials_precede_goal_and_sixsense() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert html.index('id="materialsStep"') < html.index('id="goalStep"') < html.index('id="routeStep"') < html.index('id="sensesStep"')
    assert "Where should KHALINOS begin?" in html
    assert "Tell KHALINOS the goal, requirements, and constraints." in html
    assert "/api/materials/inspect" in html
    assert "New project" in html
    assert "Improve an existing project" in html
    assert "Route recommendation" in html
    assert "/api/routes/recommend" in html
    assert "approved ToolPacks" in html
    assert 'id="routeOptions"' in html
    assert 'data-phase="route" hidden' in html
    assert "exact.length===1" in html
    assert "requestedToolpackId=exact[0].toolpack.toolpack_id;await startSixSense()" in html
    assert "Load Judge Demo inputs" in html
    assert "Choose from Project Library" in html
    assert "External project ZIP" in html
    assert 'id="toggleLocator"' in html
    assert 'id="toggleZip"' in html
    assert 'data-file-target="materials"' in html
    assert "No files selected" in html
    assert "'zip':'application/zip'" in html
    assert "txt|md|json|zip|png" in html


def test_intake_ui_explains_static_detection_and_executable_limit() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert "Files are detected statically and are not executed during intake." in html
    assert "material_inspection" in html
    assert "Sign in with Google" in html
    assert "sessionStorage" in html
    assert "function requireSignIn()" in html
    assert not re.search(r"[가-힣]", html)


def test_cloud_execution_uses_truthful_structured_camp_status() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert "Cloud heartbeat" in html
    assert "Gemini calls" in html
    assert 'id="agentCamp"' in html
    assert 'id="handoffHorse"' in html
    assert 'class="horse-sprite"' in html
    assert "horse-run-sprite.png" in html
    assert "horse-gallop" in html
    assert "Project Owner" in html
    assert "Technical Repair" in html
    assert "Role-separated Verifier" in html
    assert "function renderRun(record)" in html
    assert "record.message" in html
    assert "Each lit station reflects persisted Cloud state" in html
    assert "Trusted host gate" in html
    assert "Digest-bound" in html
    assert "Selected profile" in html
    assert "Composed Capability Packs" in html
    assert "Google Cloud execution" in html
    assert "Now working" in html
    assert 'id="milestoneTrail"' in html
    assert 'id="horseCargo"' in html
    assert "[hidden] { display:none!important; }" in html
    assert "record.status==='passed'&&record.project_id" in html
    assert "Download verified source" in html
    assert "/source.zip`" in html
    assert "function downloadProject(projectId)" in html
    assert "actual cost" not in html.lower()


def test_project_mode_can_switch_cleanly_before_goal_entry() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert 'id="startNewProject"' in html
    assert 'id="improveExisting"' in html
    assert "function clearWorkingMaterial()" in html
    assert "chooseWork('new')" in html
    assert "chooseWork('existing')" in html
    assert "function renderRoute()" in html
    assert "if(routeRecommendation){renderRoute();return;}" in html
    assert "intake=null" not in re.search(r"\$\('#changeRoute'\).*?;\}\);", html).group(0)
    assert "async function continueFromRoute()" in html
    assert "/reroute`" in html
    assert "previous.manifest_sha256===binding.manifest_sha256" in html
    assert "$('#changeRoute').addEventListener" in html
    assert "function startSixSense()" in html
    assert "requested_project_kind" in html
    assert "requested_toolpack_id" in html
    assert "requested_work_mode" in html
    assert "Outcome discovery · autonomous execution" not in html
    assert "SixSense resolves what matters" not in html


def test_goal_has_no_leading_example_and_sixsense_requires_a_real_choice() -> None:
    html = WEB.read_text(encoding="utf-8")
    goal = re.search(r'<textarea id="goal"[^>]*>', html)
    assert goal is not None
    assert "Describe the goal, required features, exclusions, and desired design" in goal.group(0)
    assert "WASD" not in goal.group(0)
    assert 'id="answerOptions"' in html
    assert "question.answer_options" in html
    assert "Confirm this choice" in html
    assert "Answer up to six questions to help KHALINOS produce the best possible result." in html
    assert "Help KHALINOS match your preferences" not in html
    assert "Answer only the questions where your preference changes the result" not in html
    assert 'id="questionCount"' in html
    assert "Question ${questionNumber} of 6" in html
    assert "senseProgress" not in html
    assert "questionKicker" not in html
    assert 'id="userChoices"' in html
    assert "KHALINOS applied professional defaults" in html
    assert "$('#answer').value=question.recommended_answer" not in html


def test_execution_camp_shows_branching_verification_and_repair_loop() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert 'class="flow-lines"' in html
    assert 'data-role="runtime"' in html
    assert "Runtime Check" in html
    assert "Bounded loop" in html
    assert "REPAIR" in html
    assert "actor.includes('runtime')" in html


def test_passed_project_can_be_opened_from_result_and_library() -> None:
    html = WEB.read_text(encoding="utf-8")
    assert "Play verified result" in html
    assert "Play result" in html
    assert "/artifact`" in html
    assert "function playProject(projectId)" in html
    assert "DOMParser" in html
