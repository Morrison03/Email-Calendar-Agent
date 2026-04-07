from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GoogleAccount
from app.services.gmail_service import list_recent_messages

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/messages")
def get_recent_gmail_messages(db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")

    messages = list_recent_messages(access_token=google_account.access_token, max_results=10)
    return {"messages": messages}