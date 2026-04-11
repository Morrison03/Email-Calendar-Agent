from __future__ import annotations

import base64
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from typing import Any, TypedDict

from googleapiclient.discovery import build


class GmailDraftResult(TypedDict):
    draft_id: str
    message_id: str
    thread_id: str


def _extract_reply_recipient(message: dict[str, Any]) -> str:
    reply_to = str(message.get("reply_to", "")).strip()
    from_header = str(message.get("from", "")).strip()

    for _, email_address in getaddresses([reply_to, from_header]):
        if email_address:
            return email_address

    _, fallback = parseaddr(from_header)
    if fallback:
        return fallback

    raise ValueError("Could not determine reply recipient from the message headers.")


def _reply_subject(subject: str) -> str:
    clean = subject.strip()
    if not clean:
        return "Re:"
    if clean.lower().startswith("re:"):
        return clean
    return f"Re: {clean}"


def create_reply_draft(
    *,
    credentials: Any,
    original_message: dict[str, Any],
    from_email: str,
    draft_body: str,
) -> GmailDraftResult:
    recipient = _extract_reply_recipient(original_message)
    subject = _reply_subject(str(original_message.get("subject", "")))
    thread_id = str(original_message.get("thread_id", ""))
    original_message_id = str(original_message.get("message_id_header", "")).strip()
    original_references = str(original_message.get("references", "")).strip()

    mime = EmailMessage()
    mime["To"] = recipient
    mime["From"] = from_email
    mime["Subject"] = subject

    if original_message_id:
        mime["In-Reply-To"] = original_message_id
        references = f"{original_references} {original_message_id}".strip() if original_references else original_message_id
        mime["References"] = references

    mime.set_content(draft_body)

    encoded_message = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")

    body: dict[str, Any] = {
        "message": {
            "raw": encoded_message,
        }
    }

    if thread_id:
        body["message"]["threadId"] = thread_id

    service = build("gmail", "v1", credentials=credentials)
    created = service.users().drafts().create(userId="me", body=body).execute()

    message = created.get("message", {})
    return {
        "draft_id": created.get("id", ""),
        "message_id": message.get("id", ""),
        "thread_id": message.get("threadId", ""),
    }