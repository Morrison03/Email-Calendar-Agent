# backend/app/services/gmail_service.py
from __future__ import annotations

import datetime as dt
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings

EmailMessage = dict[str, Any]

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def build_gmail_credentials(
    *,
    access_token: str,
    refresh_token: str | None = None,
    token_uri: str = "https://oauth2.googleapis.com/token",
    client_id: str | None = None,
    client_secret: str | None = None,
    scopes: list[str] | None = None,
    expiry: dt.datetime | None = None,
) -> Credentials:
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id or settings.google_client_id,
        client_secret=client_secret or settings.google_client_secret,
        scopes=scopes or GOOGLE_SCOPES,
        expiry=expiry,
    )


def _get_header(headers: list[dict[str, str]], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _format_internal_date(internal_date_ms: str | None) -> str:
    if not internal_date_ms:
        return ""
    try:
        timestamp = int(internal_date_ms) / 1000
        return dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def list_recent_messages(credentials: Any, max_results: int = 10) -> list[EmailMessage]:
    service = build("gmail", "v1", credentials=credentials)
    response = service.users().messages().list(userId="me", maxResults=max_results).execute()
    items = response.get("messages", [])

    messages: list[EmailMessage] = []
    for item in items:
        message_id = item.get("id")
        if not message_id:
            continue

        detail = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=[
                    "From",
                    "To",
                    "Cc",
                    "Reply-To",
                    "Subject",
                    "Date",
                    "Message-ID",
                    "References",
                    "In-Reply-To",
                ],
            )
            .execute()
        )

        payload = detail.get("payload", {})
        headers = payload.get("headers", [])

        messages.append(
            {
                "id": detail.get("id", ""),
                "thread_id": detail.get("threadId", ""),
                "from": _get_header(headers, "From"),
                "to": _get_header(headers, "To"),
                "cc": _get_header(headers, "Cc"),
                "reply_to": _get_header(headers, "Reply-To"),
                "subject": _get_header(headers, "Subject"),
                "date": _get_header(headers, "Date") or _format_internal_date(detail.get("internalDate")),
                "snippet": detail.get("snippet", ""),
                "message_id_header": _get_header(headers, "Message-ID"),
                "references": _get_header(headers, "References"),
                "in_reply_to": _get_header(headers, "In-Reply-To"),
            }
        )

    return messages