"""Gmail service helpers.

This module wraps Gmail API calls so route handlers stay small and focused on
request/response logic.
"""
from __future__ import annotations

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def build_gmail_credentials(
    access_token: str,
    refresh_token: str | None,
    token_uri: str | None,
    client_id: str,
    client_secret: str,
) -> Credentials:
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
    )


def list_recent_messages(credentials: Credentials, max_results: int = 10) -> list[dict[str, Any]]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    result = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results)
        .execute()
    )

    messages = result.get("messages", [])
    output: list[dict[str, Any]] = []

    for item in messages:
        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )

        headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

        output.append(
            {
                "id": message.get("id"),
                "thread_id": message.get("threadId"),
                "snippet": message.get("snippet"),
                "from": headers.get("From"),
                "subject": headers.get("Subject"),
                "date": headers.get("Date"),
            }
        )

    return output