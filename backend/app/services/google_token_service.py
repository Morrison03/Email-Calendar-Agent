from __future__ import annotations

from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import GoogleAccount
from app.services.gmail_service import build_gmail_credentials


def get_valid_google_credentials(db: Session, google_account: GoogleAccount) -> Credentials:
    credentials = build_gmail_credentials(
        access_token=google_account.access_token,
        refresh_token=google_account.refresh_token,
        token_uri=google_account.token_uri,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    needs_refresh = False

    if credentials.expired and credentials.refresh_token:
        needs_refresh = True
    elif google_account.expiry and google_account.expiry <= datetime.now(timezone.utc) and google_account.refresh_token:
        needs_refresh = True

    if needs_refresh:
        credentials.refresh(Request())
        google_account.access_token = credentials.token
        google_account.refresh_token = credentials.refresh_token or google_account.refresh_token
        google_account.expiry = credentials.expiry
        db.add(google_account)
        db.commit()
        db.refresh(google_account)

    return credentials