from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GoogleAccount
from app.services.gmail_service import list_recent_messages
from app.services.google_token_service import get_valid_google_credentials

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/messages")
def get_recent_gmail_messages(db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")

    credentials = get_valid_google_credentials(db=db, google_account=google_account)
    messages = list_recent_messages(credentials=credentials, max_results=10)

    return {"messages": messages}