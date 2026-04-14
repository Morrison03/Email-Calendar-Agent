from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import GoogleAccount
from app.models.meeting_queue import MeetingQueue
from app.services.email_classifier import classify_messages
from app.services.gmail_service import list_recent_messages
from app.services.google_token_service import get_valid_google_credentials


EMAIL_PATTERN = re.compile(r"<([^>]+)>")

PENDING_STATUSES = {MeetingQueue.STATUS_PENDING}
RESOLVED_STATUSES = {
    MeetingQueue.STATUS_REPLIED,
    MeetingQueue.STATUS_DISREGARDED,
}


class MeetingQueueService:
    def __init__(self) -> None:
        self._timezone = ZoneInfo(settings.app_timezone)
        self._notification_repeat_minutes = int(
            getattr(settings, "notification_repeat_minutes", 10)
        )
        self._max_pending_items = 10

    def sync_from_inbox(
        self,
        db: Session,
        *,
        google_account: GoogleAccount,
        max_results: int = 50,
    ) -> list[MeetingQueue]:
        credentials = get_valid_google_credentials(
            db=db,
            google_account=google_account,
        )
        recent_messages = list_recent_messages(
            credentials=credentials,
            max_results=max_results,
        )
        classification_result = classify_messages(recent_messages)
        classified_messages = classification_result.get("messages", [])
        return self.sync_classified_messages(
            db=db,
            google_account=google_account,
            classified_messages=classified_messages,
        )

    def sync_classified_messages(
        self,
        db: Session,
        *,
        google_account: GoogleAccount,
        classified_messages: list[dict[str, Any]],
    ) -> list[MeetingQueue]:
        thread_ids = {
            self._get_thread_id(message)
            for message in classified_messages
            if self._should_queue_message(message, google_account=google_account)
        }
        thread_ids.discard("")

        existing_items = (
            db.query(MeetingQueue)
            .filter(
                MeetingQueue.google_account_id == google_account.id,
                MeetingQueue.thread_id.in_(thread_ids) if thread_ids else False,
            )
            .all()
        )

        existing_by_thread_id = {
            item.thread_id: item
            for item in existing_items
        }

        upserted_items: list[MeetingQueue] = []

        for message in classified_messages:
            if not self._should_queue_message(message, google_account=google_account):
                continue

            thread_id = self._get_thread_id(message)
            message_id = str(message.get("id") or "").strip()

            if not thread_id or not message_id:
                continue

            item = existing_by_thread_id.get(thread_id)
            sender_email = self._extract_sender_email(message.get("from"))
            received_at = self._parse_received_at(message.get("date"))

            if item is None:
                item = MeetingQueue(
                    user_id=google_account.user_id,
                    google_account_id=google_account.id,
                    thread_id=thread_id,
                    source_message_id=message_id,
                    latest_message_id=message_id,
                    from_email=sender_email,
                    subject=self._clean_text(message.get("subject")),
                    snippet=self._clean_text(message.get("snippet")),
                    received_at=received_at,
                    status=MeetingQueue.STATUS_PENDING,
                )
                db.add(item)
                existing_by_thread_id[thread_id] = item
                upserted_items.append(item)
                continue

            item.latest_message_id = message_id
            item.from_email = sender_email
            item.subject = self._clean_text(message.get("subject"))
            item.snippet = self._clean_text(message.get("snippet"))

            if received_at is not None:
                item.received_at = received_at

            item.status = MeetingQueue.STATUS_PENDING
            upserted_items.append(item)

        if upserted_items:
            db.commit()
            for item in upserted_items:
                db.refresh(item)

        return upserted_items

    def list_pending_items(
        self,
        db: Session,
        *,
        google_account: GoogleAccount,
        limit: int | None = None,
    ) -> list[MeetingQueue]:
        query = (
            db.query(MeetingQueue)
            .filter(
                MeetingQueue.google_account_id == google_account.id,
                MeetingQueue.status == MeetingQueue.STATUS_PENDING,
            )
            .order_by(
                case((MeetingQueue.received_at.is_(None), 1), else_=0),
                MeetingQueue.received_at.desc(),
                MeetingQueue.updated_at.desc(),
            )
        )

        effective_limit = limit or self._max_pending_items
        return query.limit(effective_limit).all()

    def get_pending_count(
        self,
        db: Session,
        *,
        google_account: GoogleAccount,
    ) -> int:
        return (
            db.query(MeetingQueue)
            .filter(
                MeetingQueue.google_account_id == google_account.id,
                MeetingQueue.status == MeetingQueue.STATUS_PENDING,
            )
            .count()
        )

    def mark_disregarded(
        self,
        db: Session,
        *,
        google_account: GoogleAccount,
        queue_item_id: int,
    ) -> None:
        item = (
            db.query(MeetingQueue)
            .filter(
                MeetingQueue.id == queue_item_id,
                MeetingQueue.google_account_id == google_account.id,
            )
            .first()
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Meeting queue item not found.")

        item.status = MeetingQueue.STATUS_DISREGARDED
        db.commit()

    def mark_replied_by_thread_id(
        self,
        db: Session,
        *,
        google_account: GoogleAccount,
        thread_id: str,
    ) -> None:
        item = (
            db.query(MeetingQueue)
            .filter(
                MeetingQueue.google_account_id == google_account.id,
                MeetingQueue.thread_id == thread_id,
                MeetingQueue.status == MeetingQueue.STATUS_PENDING,
            )
            .first()
        )
        if item is None:
            return

        item.status = MeetingQueue.STATUS_REPLIED
        db.commit()

    def build_notification_payload(
        self,
        db: Session,
        *,
        google_account: GoogleAccount,
    ) -> dict[str, Any]:
        pending_items = self.list_pending_items(
            db,
            google_account=google_account,
            limit=self._max_pending_items,
        )
        pending_count = len(pending_items)

        if pending_count == 0:
            return {
                "pending_count": 0,
                "should_notify": False,
                "redirect_url": "/meeting-inbox",
                "title": "No pending meeting emails",
                "body": "",
                "reason": "no_pending_items",
            }

        redirect_url = (
            f"/reply-draft?message_id={pending_items[0].latest_message_id}"
            if pending_count == 1
            else "/meeting-inbox"
        )

        if pending_count == 1:
            item = pending_items[0]
            title = "Meeting email needs attention"
            sender = item.from_email or "Unknown sender"
            subject = item.subject or "(No subject)"
            body = f"{sender} — {subject}"
        else:
            title = f"{pending_count} meeting emails need attention"
            body = "You have pending meeting-related emails waiting for a response."

        if not self._is_within_work_hours():
            return {
                "pending_count": pending_count,
                "should_notify": False,
                "redirect_url": redirect_url,
                "title": title,
                "body": body,
                "reason": "outside_work_hours",
            }

        now = datetime.now(self._timezone)
        should_notify = any(
            item.last_notified_at is None
            or self._minutes_since(item.last_notified_at, now) >= self._notification_repeat_minutes
            for item in pending_items
        )

        if not should_notify:
            return {
                "pending_count": pending_count,
                "should_notify": False,
                "redirect_url": redirect_url,
                "title": title,
                "body": body,
                "reason": "repeat_interval_not_elapsed",
            }

        for item in pending_items:
            item.last_notified_at = now
            item.notification_count += 1
        db.commit()

        return {
            "pending_count": pending_count,
            "should_notify": True,
            "redirect_url": redirect_url,
            "title": title,
            "body": body,
            "reason": "ready",
        }

    def _should_queue_message(
        self,
        message: dict[str, Any],
        *,
        google_account: GoogleAccount,
    ) -> bool:
        category = str(message.get("category") or "").strip().casefold()
        if category != "meeting":
            return False

        sender_email = self._extract_sender_email(message.get("from"))
        if not sender_email:
            return False

        if sender_email.casefold() == google_account.google_email.casefold():
            return False

        return True

    def _get_thread_id(self, message: dict[str, Any]) -> str:
        return str(message.get("thread_id") or message.get("id") or "").strip()

    def _extract_sender_email(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""

        match = EMAIL_PATTERN.search(raw)
        if match:
            return match.group(1).strip().casefold()

        return raw.casefold()

    def _clean_text(self, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None

    def _parse_received_at(self, value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None

        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=self._timezone)

        return parsed.astimezone(self._timezone)

    def _is_within_work_hours(self) -> bool:
        now = datetime.now(self._timezone)
        current_time = now.time()
        return settings.workday_start_time <= current_time <= settings.workday_end_time

    def _minutes_since(self, earlier: datetime, later: datetime) -> int:
        earlier_value = earlier.astimezone(self._timezone)
        return int((later - earlier_value).total_seconds() // 60)