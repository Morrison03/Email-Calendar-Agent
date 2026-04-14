from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from app.core.config import settings
from app.schemas import (
    CalendarAvailabilityResult,
    CalendarBusyBlock,
    CalendarEventCreationResult,
    CalendarFreeWindow,
)


class CalendarService:
    def __init__(self) -> None:
        self._timezone_name = settings.app_timezone
        self._timezone = ZoneInfo(self._timezone_name)
        self._workday_start = settings.workday_start_time
        self._workday_end = settings.workday_end_time
        self._meeting_buffer_minutes = settings.meeting_buffer_minutes
        self._minimum_notice_minutes = settings.minimum_notice_minutes
        self._lookahead_days = settings.calendar_lookahead_days
        self._allowed_meeting_day_indexes = settings.allowed_meeting_day_indexes
        self._default_meeting_duration = settings.default_meeting_duration_minutes

    def get_availability(
        self,
        credentials: Any,
        *,
        requested_duration_minutes: int | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> CalendarAvailabilityResult:
        requested_duration = requested_duration_minutes or self._default_meeting_duration
        now_local = datetime.now(self._timezone)
        earliest_allowed_start = now_local + timedelta(minutes=self._minimum_notice_minutes)

        normalized_start = self._normalize_datetime(start_at) if start_at else earliest_allowed_start
        window_start = max(normalized_start, earliest_allowed_start)

        normalized_end = self._normalize_datetime(end_at) if end_at else None
        window_end = normalized_end or (window_start + timedelta(days=self._lookahead_days))
        if window_end <= window_start:
            window_end = window_start + timedelta(days=self._lookahead_days)

        raw_events = self._list_primary_events(
            credentials=credentials,
            time_min=window_start,
            time_max=window_end,
        )

        busy_blocks = self._build_busy_blocks(
            raw_events=raw_events,
            window_start=window_start,
            window_end=window_end,
        )
        free_windows = self._build_free_windows(
            busy_blocks=busy_blocks,
            window_start=window_start,
            window_end=window_end,
            requested_duration_minutes=requested_duration,
        )

        return CalendarAvailabilityResult(
            timezone=self._timezone_name,
            requested_duration_minutes=requested_duration,
            window_start=window_start,
            window_end=window_end,
            busy_blocks=busy_blocks,
            free_windows=free_windows,
        )

    def create_event(
        self,
        credentials: Any,
        *,
        message: dict[str, Any],
        slot_start: datetime,
        slot_end: datetime,
        slot_label: str = "",
    ) -> CalendarEventCreationResult:
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

        normalized_start = self._normalize_datetime(slot_start)
        normalized_end = self._normalize_datetime(slot_end)

        created = (
            service.events()
            .insert(
                calendarId="primary",
                body={
                    "summary": self._build_event_summary(message),
                    "description": self._build_event_description(
                        message=message,
                        slot_label=slot_label,
                    ),
                    "start": {
                        "dateTime": normalized_start.isoformat(),
                        "timeZone": self._timezone_name,
                    },
                    "end": {
                        "dateTime": normalized_end.isoformat(),
                        "timeZone": self._timezone_name,
                    },
                },
                sendUpdates="none",
                fields="id,htmlLink,summary,start,end",
            )
            .execute()
        )

        start_value = created.get("start", {}).get("dateTime")
        end_value = created.get("end", {}).get("dateTime")

        if not start_value or not end_value:
            raise ValueError("Calendar API did not return event start/end timestamps.")

        return CalendarEventCreationResult(
            event_id=created["id"],
            html_link=created.get("htmlLink"),
            summary=created.get("summary") or self._build_event_summary(message),
            start=self._normalize_datetime(datetime.fromisoformat(start_value)),
            end=self._normalize_datetime(datetime.fromisoformat(end_value)),
        )

    def _list_primary_events(
        self,
        *,
        credentials: Any,
        time_min: datetime,
        time_max: datetime,
    ) -> list[dict[str, Any]]:
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        response = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                fields="items(id,summary,start,end,status,transparency)",
            )
            .execute()
        )
        return response.get("items", [])

    def _build_busy_blocks(
        self,
        *,
        raw_events: list[dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
    ) -> list[CalendarBusyBlock]:
        busy_blocks: list[CalendarBusyBlock] = []

        for event in raw_events:
            if event.get("status") == "cancelled":
                continue

            if event.get("transparency") == "transparent":
                continue

            normalized = self._normalize_event_bounds(event)
            if normalized is None:
                continue

            event_start, event_end, is_all_day = normalized
            if event_end <= window_start or event_start >= window_end:
                continue

            clamped_start = max(event_start, window_start)
            clamped_end = min(event_end, window_end)

            if not is_all_day and self._meeting_buffer_minutes > 0:
                clamped_start = max(
                    window_start,
                    clamped_start - timedelta(minutes=self._meeting_buffer_minutes),
                )
                clamped_end = min(
                    window_end,
                    clamped_end + timedelta(minutes=self._meeting_buffer_minutes),
                )

            if clamped_end <= clamped_start:
                continue

            busy_blocks.append(
                CalendarBusyBlock(
                    start=clamped_start,
                    end=clamped_end,
                    summary=event.get("summary"),
                    is_all_day=is_all_day,
                )
            )

        return self._merge_busy_blocks(busy_blocks)

    def _normalize_event_bounds(
        self,
        event: dict[str, Any],
    ) -> tuple[datetime, datetime, bool] | None:
        start_data = event.get("start", {})
        end_data = event.get("end", {})

        if "dateTime" in start_data and "dateTime" in end_data:
            start_dt = datetime.fromisoformat(start_data["dateTime"])
            end_dt = datetime.fromisoformat(end_data["dateTime"])
            return self._normalize_datetime(start_dt), self._normalize_datetime(end_dt), False

        if "date" in start_data and "date" in end_data:
            start_date = date.fromisoformat(start_data["date"])
            end_date = date.fromisoformat(end_data["date"])
            start_dt = datetime.combine(start_date, time.min, tzinfo=self._timezone)
            end_dt = datetime.combine(end_date, time.min, tzinfo=self._timezone)
            return start_dt, end_dt, True

        return None

    def _build_free_windows(
        self,
        *,
        busy_blocks: list[CalendarBusyBlock],
        window_start: datetime,
        window_end: datetime,
        requested_duration_minutes: int,
    ) -> list[CalendarFreeWindow]:
        free_windows: list[CalendarFreeWindow] = []

        for work_start, work_end in self._build_workday_windows(
            window_start=window_start,
            window_end=window_end,
        ):
            cursor = work_start

            for busy in busy_blocks:
                if busy.end <= work_start:
                    continue
                if busy.start >= work_end:
                    break

                overlap_start = max(busy.start, work_start)
                overlap_end = min(busy.end, work_end)

                if overlap_start > cursor:
                    free_windows.append(self._build_free_window(cursor, overlap_start))

                if overlap_end > cursor:
                    cursor = overlap_end

            if cursor < work_end:
                free_windows.append(self._build_free_window(cursor, work_end))

        minimum_duration = max(requested_duration_minutes, 1)
        return [
            window
            for window in free_windows
            if window.duration_minutes >= minimum_duration
        ]

    def _build_workday_windows(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        work_windows: list[tuple[datetime, datetime]] = []
        current_day = window_start.date()
        last_day = window_end.date()

        while current_day <= last_day:
            if current_day.weekday() in self._allowed_meeting_day_indexes:
                day_start = datetime.combine(
                    current_day,
                    self._workday_start,
                    tzinfo=self._timezone,
                )
                day_end = datetime.combine(
                    current_day,
                    self._workday_end,
                    tzinfo=self._timezone,
                )

                clamped_start = max(day_start, window_start)
                clamped_end = min(day_end, window_end)

                if clamped_end > clamped_start:
                    work_windows.append((clamped_start, clamped_end))

            current_day += timedelta(days=1)

        return work_windows

    def _build_free_window(
        self,
        start: datetime,
        end: datetime,
    ) -> CalendarFreeWindow:
        return CalendarFreeWindow(
            start=start,
            end=end,
            duration_minutes=int((end - start).total_seconds() // 60),
        )

    def _merge_busy_blocks(
        self,
        busy_blocks: list[CalendarBusyBlock],
    ) -> list[CalendarBusyBlock]:
        if not busy_blocks:
            return []

        sorted_blocks = sorted(busy_blocks, key=lambda block: (block.start, block.end))
        merged: list[CalendarBusyBlock] = [sorted_blocks[0]]

        for current in sorted_blocks[1:]:
            previous = merged[-1]

            if current.start <= previous.end:
                merged[-1] = CalendarBusyBlock(
                    start=previous.start,
                    end=max(previous.end, current.end),
                    summary=previous.summary or current.summary,
                    is_all_day=previous.is_all_day or current.is_all_day,
                )
                continue

            merged.append(current)

        return merged

    def _build_event_summary(self, message: dict[str, Any]) -> str:
        subject = (message.get("subject") or "").strip()
        if subject:
            return subject
        return "Meeting"

    def _build_event_description(
        self,
        *,
        message: dict[str, Any],
        slot_label: str,
    ) -> str:
        sender = message.get("from") or "Unknown sender"
        subject = message.get("subject") or "(No subject)"
        snippet = message.get("snippet") or ""
        parts = [
            "Created from email-calendar-agent.",
            f"Sender: {sender}",
            f"Subject: {subject}",
        ]

        if slot_label:
            parts.append(f"Selected slot: {slot_label}")

        if snippet:
            parts.append("")
            parts.append("Email snippet:")
            parts.append(snippet)

        return "\n".join(parts)

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=self._timezone)
        return value.astimezone(self._timezone)