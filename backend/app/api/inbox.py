# backend/app/api/inbox.py
"""Inbox UI routes.
Renders a minimal server-side HTML inbox page using recent Gmail messages
fetched from the connected account.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GoogleAccount
from app.services.email_classifier import classify_messages
from app.services.gmail_service import list_recent_messages
from app.services.google_token_service import get_valid_google_credentials
from app.services.meeting_queue_service import MeetingQueueService

router = APIRouter(tags=["inbox"])
templates = Jinja2Templates(directory="app/templates")

meeting_queue_service = MeetingQueueService()


@router.get("/inbox", response_class=HTMLResponse)
def inbox_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")

    credentials = get_valid_google_credentials(
        db=db,
        google_account=google_account,
    )

    messages = list_recent_messages(
        credentials=credentials,
        max_results=50,
    )
    classification_result = classify_messages(messages)
    classified_messages = classification_result["messages"]

    meeting_queue_service.sync_classified_messages(
        db=db,
        google_account=google_account,
        classified_messages=classified_messages,
    )

    return templates.TemplateResponse(
        request=request,
        name="inbox.html",
        context={
            "request": request,
            "connected_email": google_account.google_email,
            "messages": classified_messages,
            "ai_available": classification_result.get("ai_available", True),
            "ai_error": classification_result.get("ai_error"),
        },
    )