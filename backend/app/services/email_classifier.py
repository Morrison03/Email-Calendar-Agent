'''
from __future__ import annotations
from typing import Any, Literal
from openai import OpenAI
from app.core.config import settings

EmailCategory = Literal["important", "meeting", "newsletter", "review"]
EmailMessage = dict[str, Any]

_ALLOWED_CATEGORIES: set[str] = {"important", "meeting", "newsletter", "review"}

#Return an API client only when the app is configured with a valid OpenAI key.
def _get_client() -> OpenAI | None:
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)

#Normalize model output into one of the allowed categories, with a safe fallback.
def _normalize_category(value: str) -> EmailCategory:
    normalized = value.strip().lower()
    if normalized in _ALLOWED_CATEGORIES:
        return normalized
    return "review"

#Build the classification prompt sent to the model using email metadata and rules.
def build_classification_prompt(*, subject: str, sender: str, snippet: str) -> str:
    return (
        "Classify this email into exactly one category:\n"
        "- important\n"
        "- meeting\n"
        "- newsletter\n"
        "- review\n\n"
        "Rules:\n"
        "- important: urgent, personal, high-priority, or clearly needs attention\n"
        "- meeting: scheduling, calendar coordination, availability, rescheduling\n"
        "- newsletter: bulk updates, subscriptions, marketing, announcements\n"
        "- review: everything else\n\n"
        "Return only the category word.\n\n"
        f"Subject: {subject or '(none)'}\n"
        f"Sender: {sender or '(unknown)'}\n"
        f"Snippet: {snippet or '(none)'}"
    )

#Classify a single email with the model and fall back to review when AI is unavailable.
def classify_email(*, subject: str, sender: str, snippet: str) -> EmailCategory:
    client = _get_client()
    if client is None:
        return "review"

    prompt = build_classification_prompt(
        subject=subject,
        sender=sender,
        snippet=snippet,
    )

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )

    content = (response.output_text or "").strip()
    return _normalize_category(content)

#Extract the expected fields from a raw message object and classify it.
def classify_message(message: EmailMessage) -> EmailCategory:
    return classify_email(
        subject=str(message.get("subject", "")),
        sender=str(message.get("from", "")),
        snippet=str(message.get("snippet", "")),
    )

#Return a new list of messages with a computed category added to each entry.
def classify_messages(messages: list[EmailMessage]) -> list[EmailMessage]:
    enriched_messages: list[EmailMessage] = []

    for message in messages:
        enriched = dict(message)
        try:
            enriched["category"] = classify_message(message)
        except Exception:
            enriched["category"] = "review"
        enriched_messages.append(enriched)

    return enriched_messages
'''

# backend/app/services/email_classifier.py
from __future__ import annotations

from typing import Any, Literal, TypedDict

from openai import OpenAI

from app.core.config import settings

EmailCategory = Literal["important", "meeting", "newsletter", "review"]
EmailMessage = dict[str, Any]


class ClassificationResult(TypedDict):
    messages: list[EmailMessage]
    ai_available: bool
    ai_error: str | None


_ALLOWED_CATEGORIES: set[str] = {"important", "meeting", "newsletter", "review"}


def _get_client() -> OpenAI | None:
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key, timeout=8.0)


def _normalize_category(value: Any) -> EmailCategory:
    if not isinstance(value, str):
        return "review"
    normalized = value.strip().lower()
    if normalized in _ALLOWED_CATEGORIES:
        return normalized
    return "review"


def _heuristic_category(message: EmailMessage) -> EmailCategory:
    text = " ".join(
        [
            str(message.get("subject", "")),
            str(message.get("from", "")),
            str(message.get("snippet", "")),
        ]
    ).lower()

    if any(word in text for word in ["meeting", "schedule", "calendar", "availability", "reschedule"]):
        return "meeting"
    if any(word in text for word in ["unsubscribe", "newsletter", "digest", "promotion", "sale"]):
        return "newsletter"
    if any(word in text for word in ["urgent", "asap", "important", "deadline", "action required"]):
        return "important"
    return "review"


def _fallback_messages(messages: list[EmailMessage]) -> list[EmailMessage]:
    enriched: list[EmailMessage] = []
    for message in messages:
        item = dict(message)
        item["category"] = _heuristic_category(message)
        enriched.append(item)
    return enriched


def _build_input(messages: list[EmailMessage]) -> list[dict[str, str]]:
    lines: list[str] = [
        "Classify each email into exactly one category.",
        "Allowed categories: important, meeting, newsletter, review.",
        "Rules:",
        "- important: urgent, personal, high-priority, or clearly needs attention",
        "- meeting: scheduling, calendar coordination, availability, rescheduling",
        "- newsletter: bulk updates, subscriptions, marketing, announcements",
        "- review: everything else",
        "Return one category per email index.",
        "",
        "Emails:",
    ]

    for index, message in enumerate(messages):
        subject = str(message.get("subject", "") or "(none)")
        sender = str(message.get("from", "") or "(unknown)")
        snippet = str(message.get("snippet", "") or "(none)")
        lines.extend(
            [
                f"Index: {index}",
                f"Subject: {subject}",
                f"Sender: {sender}",
                f"Snippet: {snippet}",
                "",
            ]
        )

    return [{"role": "user", "content": "\n".join(lines)}]


def classify_messages(messages: list[EmailMessage]) -> ClassificationResult:
    if not messages:
        return {"messages": [], "ai_available": False, "ai_error": None}

    client = _get_client()
    if client is None:
        return {
            "messages": _fallback_messages(messages),
            "ai_available": False,
            "ai_error": "OpenAI API key is missing.",
        }

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=_build_input(messages),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "email_classification_batch",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "results": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "index": {"type": "integer"},
                                        "category": {
                                            "type": "string",
                                            "enum": ["important", "meeting", "newsletter", "review"],
                                        },
                                    },
                                    "required": ["index", "category"],
                                },
                            }
                        },
                        "required": ["results"],
                    },
                }
            },
        )

        data = response.output[0].content[0].text
        results = data and __import__("json").loads(data)["results"]

        category_by_index: dict[int, EmailCategory] = {}
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                index = item.get("index")
                if isinstance(index, int) and 0 <= index < len(messages):
                    category_by_index[index] = _normalize_category(item.get("category"))

        enriched_messages: list[EmailMessage] = []
        for index, message in enumerate(messages):
            item = dict(message)
            item["category"] = category_by_index.get(index, _heuristic_category(message))
            enriched_messages.append(item)

        return {
            "messages": enriched_messages,
            "ai_available": True,
            "ai_error": None,
        }
    except Exception as exc:
        return {
            "messages": _fallback_messages(messages),
            "ai_available": False,
            "ai_error": str(exc),
        }