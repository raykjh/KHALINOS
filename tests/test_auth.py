from __future__ import annotations

import pytest

from khalinos.auth import AuthenticationUnavailable, InvalidIdentity, authenticate_bearer


def test_google_identity_uses_verified_subject_as_owner(monkeypatch) -> None:
    monkeypatch.setenv("KHALINOS_GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setattr("khalinos.auth.id_token.verify_oauth2_token", lambda *args, **kwargs: {
        "sub": "google-subject-123",
        "email": "owner@example.com",
        "email_verified": True,
        "name": "Owner",
    })
    identity = authenticate_bearer("Bearer signed-id-token")
    assert identity.owner_id == "google-subject-123"
    assert identity.email == "owner@example.com"


def test_sign_in_is_explicitly_unavailable_without_client_id(monkeypatch) -> None:
    monkeypatch.delenv("KHALINOS_GOOGLE_CLIENT_ID", raising=False)
    with pytest.raises(AuthenticationUnavailable):
        authenticate_bearer("Bearer token")


def test_unverified_email_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("KHALINOS_GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setattr("khalinos.auth.id_token.verify_oauth2_token", lambda *args, **kwargs: {
        "sub": "google-subject-123", "email": "owner@example.com", "email_verified": False,
    })
    with pytest.raises(InvalidIdentity, match="verified email"):
        authenticate_bearer("Bearer signed-id-token")
