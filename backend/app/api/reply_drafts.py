"""Reply draft preview, Gmail draft creation, event creation, and send routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import GoogleAccount
from app.schemas import (
    CalendarEventCreationResult,
    SchedulingIntentResult,
    SlotSuggestionResult,
)
from app.services.calendar_service import CalendarService
from app.services.email_classifier import classify_messages
from app.services.gmail_draft_service import create_reply_draft
from app.services.gmail_send_service import send_gmail_draft
from app.services.gmail_service import list_recent_messages
from app.services.google_token_service import get_valid_google_credentials
from app.services.meeting_queue_service import MeetingQueueService
from app.services.reply_drafter import draft_reply_for_message
from app.services.scheduling_intent_service import SchedulingIntentService
from app.services.slot_suggestion_service import SlotSuggestionService

router = APIRouter(tags=["reply-drafts"])
templates = Jinja2Templates(directory="app/templates")

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"

scheduling_intent_service = SchedulingIntentService()
calendar_service = CalendarService()
slot_suggestion_service = SlotSuggestionService()
meeting_queue_service = MeetingQueueService()


def _has_scope(google_account: GoogleAccount, scope: str) -> bool:
    raw_scopes = google_account.scopes or ""
    granted = {item.strip() for item in raw_scopes.split() if item.strip()}
    return scope in granted


def _load_classified_messages(
    db: Session,
) -> tuple[GoogleAccount, Any, list[dict[str, Any]], dict[str, Any]]:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")

    credentials = get_valid_google_credentials(db=db, google_account=google_account)
    messages = list_recent_messages(credentials=credentials, max_results=50)
    classification_result = classify_messages(messages)

    meeting_queue_service.sync_classified_messages(
        db=db,
        google_account=google_account,
        classified_messages=classification_result["messages"],
    )

    return (
        google_account,
        credentials,
        classification_result["messages"],
        classification_result,
    )


def _get_message_by_id_or_404(
    classified_messages: list[dict[str, Any]],
    message_id: str,
) -> dict[str, Any]:
    for message in classified_messages:
        if message.get("id") == message_id:
            return message

    raise HTTPException(status_code=404, detail="Message not found.")


def _build_slot_suggestions(
    *,
    credentials: Any,
    google_account: GoogleAccount,
    scheduling_intent: SchedulingIntentResult,
) -> SlotSuggestionResult:
    if not scheduling_intent.has_scheduling_intent:
        return SlotSuggestionResult(
            timezone=settings.app_timezone,
            reason="No meeting suggestions for this email.",
        )

    if not _has_scope(google_account, CALENDAR_READONLY_SCOPE):
        return SlotSuggestionResult(
            timezone=settings.app_timezone,
            reason="Reconnect Google with calendar.readonly access to load meeting suggestions.",
        )

    try:
        availability = calendar_service.get_availability(
            credentials=credentials,
            requested_duration_minutes=scheduling_intent.requested_duration_minutes,
        )
        return slot_suggestion_service.suggest_slots(
            scheduling_intent=scheduling_intent,
            availability=availability,
        )
    except Exception as exc:
        return SlotSuggestionResult(
            timezone=settings.app_timezone,
            reason=f"Could not load calendar availability: {exc}",
        )


def _build_reply_draft_context(
    *,
    request: Request,
    google_account: GoogleAccount,
    message: dict[str, Any],
    draft: str,
    classification_result: dict[str, Any],
    draft_ai_available: bool,
    draft_ai_error: str | None,
    draft_created: bool,
    created_draft_id: str,
    create_error: str,
    draft_sent: bool,
    sent_message_id: str,
    send_error: str,
    scheduling_intent: SchedulingIntentResult,
    slot_suggestions: SlotSuggestionResult,
    event_created: bool,
    created_event: CalendarEventCreationResult | None,
    event_create_error: str,
) -> dict[str, Any]:
    return {
        "request": request,
        "message": message,
        "message_id": message.get("id", ""),
        "connected_email": google_account.google_email,
        "draft": draft,
        "draft_ai_available": draft_ai_available,
        "draft_ai_error": draft_ai_error,
        "classification_ai_available": classification_result.get("ai_available", True),
        "classification_ai_error": classification_result.get("ai_error"),
        "has_gmail_compose_scope": _has_scope(google_account, GMAIL_COMPOSE_SCOPE),
        "has_calendar_read_scope": _has_scope(google_account, CALENDAR_READONLY_SCOPE),
        "has_calendar_write_scope": _has_scope(google_account, CALENDAR_EVENTS_SCOPE),
        "draft_created": draft_created,
        "created_draft_id": created_draft_id,
        "create_error": create_error,
        "draft_sent": draft_sent,
        "sent_message_id": sent_message_id,
        "send_error": send_error,
        "scheduling_intent": scheduling_intent,
        "slot_suggestions": slot_suggestions,
        "event_created": event_created,
        "created_event": created_event,
        "event_create_error": event_create_error,
    }


@router.get("/reply-draft", response_class=HTMLResponse)
def reply_draft_page(
    request: Request,
    message_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account, credentials, classified_messages, classification_result = _load_classified_messages(db)
    message = _get_message_by_id_or_404(classified_messages, message_id)
    draft_result = draft_reply_for_message(message)
    scheduling_intent = scheduling_intent_service.analyze_message(message)
    slot_suggestions = _build_slot_suggestions(
        credentials=credentials,
        google_account=google_account,
        scheduling_intent=scheduling_intent,
    )

    context = _build_reply_draft_context(
        request=request,
        google_account=google_account,
        message=message,
        draft=draft_result["draft"],
        classification_result=classification_result,
        draft_ai_available=draft_result["ai_available"],
        draft_ai_error=draft_result["ai_error"],
        draft_created=False,
        created_draft_id="",
        create_error="",
        draft_sent=False,
        sent_message_id="",
        send_error="",
        scheduling_intent=scheduling_intent,
        slot_suggestions=slot_suggestions,
        event_created=False,
        created_event=None,
        event_create_error="",
    )

    return templates.TemplateResponse(
        request=request,
        name="reply_draft.html",
        context=context,
    )


@router.post("/calendar-event/create", response_class=HTMLResponse)
def create_calendar_event_page(
    request: Request,
    message_id: str = Form(...),
    draft: str = Form(...),
    slot_start: str = Form(...),
    slot_end: str = Form(...),
    slot_label: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account, credentials, classified_messages, classification_result = _load_classified_messages(db)

    if not _has_scope(google_account, CALENDAR_EVENTS_SCOPE):
        raise HTTPException(
            status_code=403,
            detail="Google account must be reconnected with calendar.events scope.",
        )

    message = _get_message_by_id_or_404(classified_messages, message_id)
    scheduling_intent = scheduling_intent_service.analyze_message(message)
    slot_suggestions = _build_slot_suggestions(
        credentials=credentials,
        google_account=google_account,
        scheduling_intent=scheduling_intent,
    )

    created_event: CalendarEventCreationResult | None = None
    event_created = False
    event_create_error = ""

    try:
        created_event = calendar_service.create_event(
            credentials=credentials,
            message=message,
            slot_start=datetime.fromisoformat(slot_start),
            slot_end=datetime.fromisoformat(slot_end),
            slot_label=slot_label,
        )
        event_created = True
    except Exception as exc:
        event_create_error = str(exc)

    context = _build_reply_draft_context(
        request=request,
        google_account=google_account,
        message=message,
        draft=draft,
        classification_result=classification_result,
        draft_ai_available=True,
        draft_ai_error=None,
        draft_created=False,
        created_draft_id="",
        create_error="",
        draft_sent=False,
        sent_message_id="",
        send_error="",
        scheduling_intent=scheduling_intent,
        slot_suggestions=slot_suggestions,
        event_created=event_created,
        created_event=created_event,
        event_create_error=event_create_error,
    )

    return templates.TemplateResponse(
        request=request,
        name="reply_draft.html",
        context=context,
    )


@router.post("/reply-draft/create", response_class=HTMLResponse)
def create_reply_draft_page(
    request: Request,
    message_id: str = Form(...),
    draft: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account, credentials, classified_messages, classification_result = _load_classified_messages(db)

    if not _has_scope(google_account, GMAIL_COMPOSE_SCOPE):
        raise HTTPException(
            status_code=403,
            detail="Google account must be reconnected with gmail.compose scope.",
        )

    message = _get_message_by_id_or_404(classified_messages, message_id)
    scheduling_intent = scheduling_intent_service.analyze_message(message)
    slot_suggestions = _build_slot_suggestions(
        credentials=credentials,
        google_account=google_account,
        scheduling_intent=scheduling_intent,
    )

    created_draft_id = ""
    create_error = ""
    draft_created = False

    try:
        created = create_reply_draft(
            credentials=credentials,
            original_message=message,
            from_email=google_account.google_email,
            draft_body=draft,
        )
        created_draft_id = created["draft_id"]
        draft_created = True
    except Exception as exc:
        create_error = str(exc)

    context = _build_reply_draft_context(
        request=request,
        google_account=google_account,
        message=message,
        draft=draft,
        classification_result=classification_result,
        draft_ai_available=True,
        draft_ai_error=None,
        draft_created=draft_created,
        created_draft_id=created_draft_id,
        create_error=create_error,
        draft_sent=False,
        sent_message_id="",
        send_error="",
        scheduling_intent=scheduling_intent,
        slot_suggestions=slot_suggestions,
        event_created=False,
        created_event=None,
        event_create_error="",
    )

    return templates.TemplateResponse(
        request=request,
        name="reply_draft.html",
        context=context,
    )


@router.post("/reply-draft/send", response_class=HTMLResponse)
def send_reply_draft_page(
    request: Request,
    message_id: str = Form(...),
    draft: str = Form(...),
    draft_id: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account, credentials, classified_messages, classification_result = _load_classified_messages(db)

    if not _has_scope(google_account, GMAIL_COMPOSE_SCOPE):
        raise HTTPException(
            status_code=403,
            detail="Google account must be reconnected with gmail.compose scope.",
        )

    message = _get_message_by_id_or_404(classified_messages, message_id)
    scheduling_intent = scheduling_intent_service.analyze_message(message)
    slot_suggestions = _build_slot_suggestions(
        credentials=credentials,
        google_account=google_account,
        scheduling_intent=scheduling_intent,
    )

    draft_sent = False
    sent_message_id = ""
    send_error = ""

    try:
        sent = send_gmail_draft(credentials=credentials, draft_id=draft_id)
        draft_sent = True
        sent_message_id = sent["message_id"]

        thread_id = str(message.get("thread_id") or "").strip()
        if thread_id:
            meeting_queue_service.mark_replied_by_thread_id(
                db=db,
                google_account=google_account,
                thread_id=thread_id,
            )
    except Exception as exc:
        send_error = str(exc)

    context = _build_reply_draft_context(
        request=request,
        google_account=google_account,
        message=message,
        draft=draft,
        classification_result=classification_result,
        draft_ai_available=True,
        draft_ai_error=None,
        draft_created=True,
        created_draft_id=draft_id,
        create_error="",
        draft_sent=draft_sent,
        sent_message_id=sent_message_id,
        send_error=send_error,
        scheduling_intent=scheduling_intent,
        slot_suggestions=slot_suggestions,
        event_created=False,
        created_event=None,
        event_create_error="",
    )

    return templates.TemplateResponse(
        request=request,
        name="reply_draft.html",
        context=context,
    )