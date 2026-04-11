"""Database session dependency helpers.

FastAPI routes use this generator to open a database session for each request
and close it safely afterward.
"""
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.base import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()