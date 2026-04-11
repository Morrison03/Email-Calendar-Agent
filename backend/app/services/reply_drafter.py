# backend/app/services/reply_drafter.py
from __future__ import annotations

from typing import Any, Literal, TypedDict

from openai import OpenAI

from app.core.config import settings

EmailCategory = Literal["important", "meeting", "newsletter", "review"]
EmailMessage = dict[str, Any]


class ReplyDraftResult(TypedDict):
    draft: str
    ai_available: bool
    ai_error: str | None


def _get_client() -> OpenAI | None:
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key, timeout=10.0)


def _normalize_category(value: Any) -> EmailCategory:
    if not isinstance(value, str):
        return "review"

    normalized = value.strip().lower()
    if normalized in {"important", "meeting", "newsletter", "review"}:
        return normalized  # type: ignore[return-value]

    return "review"


def _build_reply_prompt(
    *,
    sender: str,
    subject: str,
    snippet: str,
    category: EmailCategory,
) -> str:
    return (
        "Write a concise email reply draft.\n"
        "Requirements:\n"
        "- Output plain text only\n"
        "- Do not include a subject line\n"
        "- Keep it short and natural\n"
        "- Be professional and helpful\n"
        "- Do not invent facts that were not provided\n"
        "- If the message is a newsletter or promo, draft a polite no-reply-needed response only if appropriate\n"
        "- If no reply is appropriate, return exactly: NO_REPLY_NEEDED\n"
        "- For meeting emails, suggest a brief cooperative response without inventing calendar availability\n"
        "- For important emails, prioritize clarity and action\n"
        "- For review emails, give a neutral helpful response\n\n"
        f"Category: {category}\n"
        f"Sender: {sender or '(unknown)'}\n"
        f"Subject: {subject or '(no subject)'}\n"
        f"Snippet: {snippet or '(no snippet)'}\n"
    )


def _fallback_draft(*, category: EmailCategory) -> str:
    if category == "meeting":
        return (
            "Thanks for reaching out. I would be happy to coordinate a time. "
            "Please share a few options that work for you."
        )

    if category == "important":
        return (
            "Thanks for the note. I received this and will review it shortly."
        )

    if category == "newsletter":
        return "NO_REPLY_NEEDED"

    return (
        "Thanks for your email. I received it and will review it soon."
    )


def draft_reply(
    *,
    sender: str,
    subject: str,
    snippet: str,
    category: str,
) -> ReplyDraftResult:
    normalized_category = _normalize_category(category)
    client = _get_client()

    if client is None:
        return {
            "draft": _fallback_draft(category=normalized_category),
            "ai_available": False,
            "ai_error": "OpenAI API key is missing.",
        }

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=_build_reply_prompt(
                sender=sender,
                subject=subject,
                snippet=snippet,
                category=normalized_category,
            ),
        )
        draft = (response.output_text or "").strip()

        if not draft:
            draft = _fallback_draft(category=normalized_category)

        return {
            "draft": draft,
            "ai_available": True,
            "ai_error": None,
        }
    except Exception as exc:
        return {
            "draft": _fallback_draft(category=normalized_category),
            "ai_available": False,
            "ai_error": str(exc),
        }


def draft_reply_for_message(message: EmailMessage) -> ReplyDraftResult:
    return draft_reply(
        sender=str(message.get("from", "")),
        subject=str(message.get("subject", "")),
        snippet=str(message.get("snippet", "")),
        category=str(message.get("category", "review")),
    )