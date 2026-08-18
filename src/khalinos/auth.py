"""Minimal Google OpenID Connect identity boundary for private project data."""

from __future__ import annotations

import os
from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


class AuthenticationUnavailable(RuntimeError):
    pass


class InvalidIdentity(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    owner_id: str
    email: str
    name: str


def google_client_id() -> str:
    return os.environ.get("KHALINOS_GOOGLE_CLIENT_ID", "").strip()


def authenticate_bearer(authorization: str | None) -> Identity:
    client_id = google_client_id()
    if not client_id:
        raise AuthenticationUnavailable("Google sign-in is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidIdentity("Google sign-in is required")
    credential = authorization.removeprefix("Bearer ").strip()
    if not credential:
        raise InvalidIdentity("Google identity credential is missing")
    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            audience=client_id,
        )
    except Exception as exc:
        raise InvalidIdentity("Google identity credential is invalid") from exc
    owner_id = str(claims.get("sub", ""))
    email = str(claims.get("email", ""))
    if not owner_id or not email or claims.get("email_verified") is not True:
        raise InvalidIdentity("Google identity must include a verified email")
    return Identity(owner_id=owner_id, email=email, name=str(claims.get("name", email)))
