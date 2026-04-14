from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MeetingQueue(Base):
    __tablename__ = "meeting_queue"

    __table_args__ = (
        UniqueConstraint(
            "google_account_id",
            "thread_id",
            name="uq_meeting_queue_google_account_thread",
        ),
    )

    STATUS_PENDING = "pending"
    STATUS_REPLIED = "replied"
    STATUS_DISREGARDED = "disregarded"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    google_account_id: Mapped[int] = mapped_column(
        ForeignKey("google_accounts.id"),
        nullable=False,
        index=True,
    )

    thread_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_message_id: Mapped[str] = mapped_column(String(255), nullable=False)

    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=STATUS_PENDING,
        server_default=STATUS_PENDING,
        index=True,
    )

    notification_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User")
    google_account = relationship("GoogleAccount")

    def __repr__(self) -> str:
        return (
            f"MeetingQueue(id={self.id!r}, thread_id={self.thread_id!r}, "
            f"status={self.status!r}, subject={self.subject!r})"
        )