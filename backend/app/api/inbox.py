from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GoogleAccount
from app.services.gmail_service import list_recent_messages
from app.services.google_token_service import get_valid_google_credentials

router = APIRouter(tags=["inbox"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/inbox", response_class=HTMLResponse)
def inbox_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    google_account = db.query(GoogleAccount).first()
    if google_account is None:
        raise HTTPException(status_code=404, detail="No connected Google account found.")

    credentials = get_valid_google_credentials(db=db, google_account=google_account)
    messages = list_recent_messages(credentials=credentials, max_results=15)

    return templates.TemplateResponse(
        request=request,
        name="inbox.html",
        context={
            "request": request,
            "messages": messages,
            "connected_email": google_account.google_email,
        },
    )