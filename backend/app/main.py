"""FastAPI application entrypoint.

This file creates the app, registers routes, and ensures database tables
exist during local development startup.
"""
# backend/app/main.py
from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.gmail import router as gmail_router
from app.api.inbox import router as inbox_router
from app.api.reply_drafts import router as reply_drafts_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(inbox_router)
app.include_router(reply_drafts_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}