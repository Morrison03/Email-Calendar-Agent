# backend/app/integrations/google_oauth.py
from __future__ import annotations

from typing import Any

import requests
from google_auth_oauthlib.flow import Flow

from app.core.config import settings

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def build_google_flow(*, state: str | None = None, code_verifier: str | None = None) -> Flow:
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=GOOGLE_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.google_redirect_uri
    if code_verifier:
        flow.code_verifier = code_verifier
    return flow


def create_authorization_url(*, state: str, code_verifier: str) -> tuple[str, str]:
    flow = build_google_flow(state=state, code_verifier=code_verifier)
    authorization_url, returned_state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    return authorization_url, returned_state


def fetch_google_token(
    *,
    code: str,
    state: str | None = None,
    code_verifier: str | None = None,
) -> dict[str, Any]:
    flow = build_google_flow(state=state, code_verifier=code_verifier)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "scopes": list(credentials.scopes or []),
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }


def fetch_tokens_from_callback(
    *,
    code: str,
    state: str | None = None,
    code_verifier: str | None = None,
) -> dict[str, Any]:
    return fetch_google_token(
        code=code,
        state=state,
        code_verifier=code_verifier,
    )


def fetch_google_userinfo(*, access_token: str) -> dict[str, Any]:
    response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()