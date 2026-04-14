from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import GoogleAccount
from app.services.meeting_queue_service import MeetingQueueService


router = APIRouter(tags=["meeting-inbox"])
templates = Jinja2Templates(directory="app/templates")
meeting_queue_service = MeetingQueueService()


def _get_connected_google_account(db: Session) -> GoogleAccount:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")
    return google_account


@router.get("/meeting-inbox", response_class=HTMLResponse)
def meeting_inbox_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    google_account = _get_connected_google_account(db)

    meeting_queue_service.sync_from_inbox(
        db,
        google_account=google_account,
        max_results=50,
    )

    meeting_items = meeting_queue_service.list_pending_items(
        db,
        google_account=google_account,
        limit=10,
    )

    return templates.TemplateResponse(
        request=request,
        name="meeting_inbox.html",
        context={
            "request": request,
            "connected_email": google_account.google_email,
            "meeting_items": meeting_items,
            "pending_count": len(meeting_items),
            "notification_poll_seconds": int(
                getattr(settings, "notification_poll_seconds", 60)
            ),
            "notification_repeat_minutes": int(
                getattr(settings, "notification_repeat_minutes", 10)
            ),
        },
    )


@router.post("/meeting-inbox/disregard")
def disregard_meeting_item(
    queue_item_id: int = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    google_account = _get_connected_google_account(db)

    meeting_queue_service.mark_disregarded(
        db,
        google_account=google_account,
        queue_item_id=queue_item_id,
    )

    return RedirectResponse(url="/meeting-inbox", status_code=303)