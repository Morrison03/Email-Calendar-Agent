"""FastAPI application entrypoint.

This file creates the app, registers routes, and ensures database tables
exist during local development startup.
"""
from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.gmail import router as gmail_router
from app.api.inbox import router as inbox_router
from app.db.base import Base, engine
from app.models import GoogleAccount, User

app = FastAPI(title="Email Calendar Agent")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(inbox_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}