from __future__ import annotations

from threading import Lock
from typing import Any

import httpx
from google_auth_oauthlib.flow import Flow

from app.core.config import settings

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

_pkce_store: dict[str, str] = {}
_pkce_lock = Lock()


def build_google_flow(state: str | None = None, code_verifier: str | None = None) -> Flow:
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_SCOPES,
        state=state,
        redirect_uri=settings.google_redirect_uri,
        code_verifier=code_verifier,
    )


def create_authorization_url(state: str) -> tuple[str, str]:
    flow = build_google_flow(state=state)
    authorization_url, returned_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    if not flow.code_verifier:
        raise RuntimeError("OAuth flow did not generate a PKCE code_verifier.")

    with _pkce_lock:
        _pkce_store[returned_state] = flow.code_verifier

    return authorization_url, returned_state


def fetch_tokens_from_callback(code: str, state: str) -> dict[str, Any]:
    with _pkce_lock:
        code_verifier = _pkce_store.pop(state, None)

    if not code_verifier:
        raise RuntimeError(
            "Missing PKCE code_verifier for this OAuth state. Start login again from /auth/google/start."
        )

    flow = build_google_flow(state=state, code_verifier=code_verifier)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    return {
        "token": getattr(credentials, "token", None),
        "refresh_token": getattr(credentials, "refresh_token", None),
        "token_uri": getattr(credentials, "token_uri", None),
        "client_id": getattr(credentials, "client_id", None),
        "client_secret": getattr(credentials, "client_secret", None),
        "scopes": list(getattr(credentials, "scopes", []) or []),
        "expiry": credentials.expiry.isoformat() if getattr(credentials, "expiry", None) else None,
    }


async def fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()