"""FastAPI application entrypoint.

This file creates the app, registers routes, and ensures database tables
exist during local development startup.
"""
# backend/app/main.py
from __future__ import annotations

import os

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.gmail import router as gmail_router
from app.api.inbox import router as inbox_router
from app.api.reply_drafts import router as reply_drafts_router
from app.core.config import settings

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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}