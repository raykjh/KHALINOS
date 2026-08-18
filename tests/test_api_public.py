from __future__ import annotations

from fastapi.testclient import TestClient

from khalinos.api import app


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


def test_public_config_exposes_only_the_oauth_client_identifier(monkeypatch) -> None:
    monkeypatch.setenv("KHALINOS_GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
    payload = client.get("/api/config").json()
    assert payload == {
        "google_sign_in_enabled": True,
        "google_client_id": "client.apps.googleusercontent.com",
        "judge_demo_enabled": True,
    }
