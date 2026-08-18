from __future__ import annotations

from fastapi.testclient import TestClient

import khalinos.api as api
from khalinos.api import app
from khalinos.godot_toolpack import GODOT_TOPOLOGY_TOOLPACK
from khalinos.models import UserBrief


client = TestClient(app)


def test_public_judge_demo_requires_no_identity() -> None:
    response = client.get("/api/demo/project")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_name"] == "PUZZLE Input Repair"
    assert "WASD" in payload["goal"]


def test_private_project_library_fails_closed_without_oauth_configuration(monkeypatch) -> None:
    monkeypatch.delenv("KHALINOS_GOOGLE_CLIENT_ID", raising=False)
    response = client.get("/api/projects")
    assert response.status_code == 503
    assert response.json()["detail"] == "Google sign-in is not configured"


def test_private_playable_artifact_fails_closed_without_identity(monkeypatch) -> None:
    monkeypatch.delenv("KHALINOS_GOOGLE_CLIENT_ID", raising=False)
    response = client.get(f"/api/projects/{'a' * 32}/artifact")
    assert response.status_code == 503
    assert response.json()["detail"] == "Google sign-in is not configured"


def test_public_config_exposes_only_the_oauth_client_identifier(monkeypatch) -> None:
    monkeypatch.setenv("KHALINOS_GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
    payload = client.get("/api/config").json()
    assert payload == {
        "google_sign_in_enabled": True,
        "google_client_id": "client.apps.googleusercontent.com",
        "judge_demo_enabled": True,
    }


def test_queue_run_selects_toolpack_from_exact_project_kind_and_work_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeStore:
        def create(self, record, brief) -> None:
            captured["record"] = record
            captured["brief"] = brief

        def update(self, record) -> None:
            captured["updated"] = record

    def select(*, project_kind: str, work_mode: str, requested_toolpack_id=None):
        captured["selection"] = (project_kind, work_mode, requested_toolpack_id)
        return GODOT_TOPOLOGY_TOOLPACK

    monkeypatch.setattr(api, "CloudRunStore", FakeStore)
    monkeypatch.setattr(api.APPROVED_TOOLPACKS, "select", select)
    monkeypatch.setattr(api, "dispatch_run", lambda run_id: {"execution": run_id})
    brief = UserBrief(
        project_name="Route Observatory",
        goal="Create a bounded offline Godot topology with an arrival and verified result screen.",
        acceptance_criteria=[
            "The project opens on an arrival screen.",
            "Every declared screen loads in headless verification.",
        ],
        authorized_output_files=["placeholder.txt"],
    )

    result = api.queue_run(
        brief,
        owner_id="owner@example.com",
        project_id="a" * 32,
        project_kind="godot",
    )

    assert captured["selection"] == ("godot", "new_product_build", None)
    assert captured["record"].toolpack_binding == GODOT_TOPOLOGY_TOOLPACK.binding()
    assert captured["brief"].authorized_output_files == list(
        GODOT_TOPOLOGY_TOOLPACK.manifest.output.authorized_paths
    )
    assert result["record"]["work_mode"] == "new_product_build"
