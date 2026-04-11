from __future__ import annotations

from typing import Any, TypedDict

from googleapiclient.discovery import build


class GmailSendDraftResult(TypedDict):
    message_id: str
    thread_id: str
    label_ids: list[str]


def send_gmail_draft(*, credentials: Any, draft_id: str) -> GmailSendDraftResult:
    service = build("gmail", "v1", credentials=credentials)
    sent = (
        service.users()
        .drafts()
        .send(
            userId="me",
            body={
                "id": draft_id,
            },
        )
        .execute()
    )

    return {
        "message_id": sent.get("id", ""),
        "thread_id": sent.get("threadId", ""),
        "label_ids": sent.get("labelIds", []),
    }