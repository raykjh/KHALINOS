from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import khalinos.api as api
from khalinos.api import app
from khalinos.auth import Identity
from khalinos.godot_toolpack import GODOT_TOPOLOGY_TOOLPACK
from khalinos.models import IntakeCreate, UserBrief


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
        work_mode="new_product_build",
    )

    assert captured["selection"] == ("godot", "new_product_build", None)
    assert captured["record"].toolpack_binding == GODOT_TOPOLOGY_TOOLPACK.binding()
    assert captured["brief"].authorized_output_files == list(
        GODOT_TOPOLOGY_TOOLPACK.manifest.output.authorized_paths
    )
    assert result["record"]["work_mode"] == "new_product_build"
    assert captured["brief"].max_repairs_per_quest == 0


def test_public_godot_route_rejects_unprovable_gameplay_criteria() -> None:
    brief = UserBrief(
        project_name="Stealth Game",
        goal="Create a complete stealth game with connected screens and a playable guard encounter.",
        acceptance_criteria=[
            "The project opens on an arrival screen.",
            "Enemy gameplay and keyboard input work correctly.",
        ],
        authorized_output_files=["placeholder.txt"],
    )
    with pytest.raises(ValueError, match="cannot verify"):
        api.validate_godot_topology_brief(brief)


async def test_new_intake_requires_an_explicit_approved_runtime() -> None:
    request = IntakeCreate(
        project_name="Route Observatory",
        goal="Create a bounded project with a clearly verified primary workflow.",
    )
    with pytest.raises(api.HTTPException) as raised:
        await api.create_intake(
            request,
            Identity(owner_id="owner", email="owner@example.com", name="Owner"),
        )
    assert raised.value.status_code == 422
    assert "approved new-project runtime" in raised.value.detail


async def test_godot_existing_project_mode_remains_fail_closed() -> None:
    request = IntakeCreate(
        project_name="Existing Godot",
        goal="Repair an existing Godot product without changing its approved behavior.",
        selected_project_id="a" * 32,
        requested_project_kind="godot",
        requested_work_mode="existing_project_repair",
    )
    with pytest.raises(api.HTTPException) as raised:
        await api.create_intake(
            request,
            Identity(owner_id="owner", email="owner@example.com", name="Owner"),
        )
    assert raised.value.status_code == 422
    assert "new topology projects only" in raised.value.detail
