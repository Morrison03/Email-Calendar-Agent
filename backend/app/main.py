from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.db.base import Base, engine
from app.models import GoogleAccount, User

app = FastAPI(title="Email Calendar Agent")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}