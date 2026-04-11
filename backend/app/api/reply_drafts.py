# backend/app/api/reply_drafts.py
"""Reply draft preview routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GoogleAccount
from app.services.gmail_service import list_recent_messages
from app.services.google_token_service import get_valid_google_credentials
from app.services.email_classifier import classify_messages
from app.services.reply_drafter import draft_reply_for_message

router = APIRouter(tags=["reply-drafts"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/reply-draft", response_class=HTMLResponse)
def reply_draft_page(
    request: Request,
    message_index: int = Query(..., ge=0),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")

    credentials = get_valid_google_credentials(db=db, google_account=google_account)
    messages = list_recent_messages(credentials=credentials, max_results=10)

    classification_result = classify_messages(messages)
    classified_messages = classification_result["messages"]

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
        },
    )