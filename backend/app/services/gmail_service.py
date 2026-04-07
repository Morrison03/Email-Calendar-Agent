from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build


def build_gmail_client(access_token: str):
    return build(
        "gmail",
        "v1",
        developerKey=None,
        credentials=None,
        cache_discovery=False,
    )


def list_recent_messages(access_token: str, max_results: int = 10) -> list[dict[str, Any]]:
    from google.oauth2.credentials import Credentials

    credentials = Credentials(token=access_token)
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
            .get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
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