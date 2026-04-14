from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GoogleAccount
from app.services.meeting_queue_service import MeetingQueueService


router = APIRouter(tags=["notifications"])
meeting_queue_service = MeetingQueueService()


@router.get("/notifications/meeting-status")
def meeting_status_notification(
    db: Session = Depends(get_db),
) -> JSONResponse:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        return JSONResponse(
            {
                "pending_count": 0,
                "should_notify": False,
                "redirect_url": "/inbox",
                "title": "No connected Google account",
                "body": "",
            }
        )

    meeting_queue_service.sync_from_inbox(
        db,
        google_account=google_account,
        max_results=50,
    )

    payload = meeting_queue_service.build_notification_payload(
        db,
        google_account=google_account,
    )
    return JSONResponse(payload)