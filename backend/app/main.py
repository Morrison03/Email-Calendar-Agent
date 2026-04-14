"""FastAPI application entrypoint.

This file creates the app, registers routes, and ensures database tables
exist during local development startup.
"""
# backend/app/main.py
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.gmail import router as gmail_router
from app.api.inbox import router as inbox_router
from app.api.meeting_inbox import router as meeting_inbox_router
from app.api.notifications import router as notifications_router
from app.api.reply_drafts import router as reply_drafts_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
import app.models

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = settings.oauthlib_relax_token_scope

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=False,
)

app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(inbox_router)
app.include_router(reply_drafts_router)
app.include_router(meeting_inbox_router)
app.include_router(notifications_router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}