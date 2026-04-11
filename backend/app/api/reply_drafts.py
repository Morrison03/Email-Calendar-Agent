"""Reply draft preview, Gmail draft creation, and send routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GoogleAccount
from app.services.email_classifier import classify_messages
from app.services.gmail_draft_service import create_reply_draft
from app.services.gmail_send_service import send_gmail_draft
from app.services.gmail_service import list_recent_messages
from app.services.google_token_service import get_valid_google_credentials
from app.services.reply_drafter import draft_reply_for_message

router = APIRouter(tags=["reply-drafts"])
templates = Jinja2Templates(directory="app/templates")

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"


def _has_scope(google_account: GoogleAccount, scope: str) -> bool:
    raw_scopes = google_account.scopes or ""
    granted = {item.strip() for item in raw_scopes.split() if item.strip()}
    return scope in granted


def _load_classified_messages(
    db: Session,
) -> tuple[GoogleAccount, Any, list[dict], dict]:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")

    credentials = get_valid_google_credentials(db=db, google_account=google_account)
    messages = list_recent_messages(credentials=credentials, max_results=10)
    classification_result = classify_messages(messages)

    return (
        google_account,
        credentials,
        classification_result["messages"],
        classification_result,
    )


@router.get("/reply-draft", response_class=HTMLResponse)
def reply_draft_page(
    request: Request,
    message_index: int = Query(..., ge=0),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account, _, classified_messages, classification_result = _load_classified_messages(db)

    if message_index >= len(classified_messages):
        raise HTTPException(status_code=404, detail="Message index out of range.")

    message = classified_messages[message_index]
    draft_result = draft_reply_for_message(message)

    return templates.TemplateResponse(
        request=request,
        name="reply_draft.html",
        context={
            "request": request,
            "message": message,
            "message_index": message_index,
            "connected_email": google_account.google_email,
            "draft": draft_result["draft"],
            "draft_ai_available": draft_result["ai_available"],
            "draft_ai_error": draft_result["ai_error"],
            "classification_ai_available": classification_result["ai_available"],
            "classification_ai_error": classification_result["ai_error"],
            "has_gmail_compose_scope": _has_scope(
                google_account,
                GMAIL_COMPOSE_SCOPE,
            ),
            "draft_created": False,
            "created_draft_id": "",
            "create_error": "",
            "draft_sent": False,
            "sent_message_id": "",
            "send_error": "",
        },
    )


@router.post("/reply-draft/create", response_class=HTMLResponse)
def create_reply_draft_page(
    request: Request,
    message_index: int = Form(...),
    draft: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account, credentials, classified_messages, classification_result = _load_classified_messages(db)

    if not _has_scope(google_account, GMAIL_COMPOSE_SCOPE):
        raise HTTPException(
            status_code=403,
            detail="Google account must be reconnected with gmail.compose scope.",
        )

    if message_index < 0 or message_index >= len(classified_messages):
        raise HTTPException(status_code=404, detail="Message index out of range.")

    message = classified_messages[message_index]

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

    return templates.TemplateResponse(
        request=request,
        name="reply_draft.html",
        context={
            "request": request,
            "message": message,
            "message_index": message_index,
            "connected_email": google_account.google_email,
            "draft": draft,
            "draft_ai_available": True,
            "draft_ai_error": None,
            "classification_ai_available": classification_result["ai_available"],
            "classification_ai_error": classification_result["ai_error"],
            "has_gmail_compose_scope": _has_scope(
                google_account,
                GMAIL_COMPOSE_SCOPE,
            ),
            "draft_created": draft_created,
            "created_draft_id": created_draft_id,
            "create_error": create_error,
            "draft_sent": False,
            "sent_message_id": "",
            "send_error": "",
        },
    )


@router.post("/reply-draft/send", response_class=HTMLResponse)
def send_reply_draft_page(
    request: Request,
    message_index: int = Form(...),
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

    if message_index < 0 or message_index >= len(classified_messages):
        raise HTTPException(status_code=404, detail="Message index out of range.")

    message = classified_messages[message_index]

    draft_sent = False
    sent_message_id = ""
    send_error = ""

    try:
        sent = send_gmail_draft(credentials=credentials, draft_id=draft_id)
        draft_sent = True
        sent_message_id = sent["message_id"]
    except Exception as exc:
        send_error = str(exc)

    return templates.TemplateResponse(
        request=request,
        name="reply_draft.html",
        context={
            "request": request,
            "message": message,
            "message_index": message_index,
            "connected_email": google_account.google_email,
            "draft": draft,
            "draft_ai_available": True,
            "draft_ai_error": None,
            "classification_ai_available": classification_result["ai_available"],
            "classification_ai_error": classification_result["ai_error"],
            "has_gmail_compose_scope": _has_scope(
                google_account,
                GMAIL_COMPOSE_SCOPE,
            ),
            "draft_created": True,
            "created_draft_id": draft_id,
            "create_error": "",
            "draft_sent": draft_sent,
            "sent_message_id": sent_message_id,
            "send_error": send_error,
        },
    )