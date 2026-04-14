from __future__ import annotations

import re
from calendar import month_abbr
from datetime import date, datetime, time, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.schemas import (
    CalendarAvailabilityResult,
    SlotSuggestionResult,
    SuggestedMeetingSlot,
    SchedulingIntentResult,
)

WEEKDAY_NAME_TO_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

PART_OF_DAY_RANGES = {
    "morning": (9 * 60, 12 * 60),
    "afternoon": (12 * 60, 17 * 60),
    "evening": (17 * 60, 20 * 60),
    "noon": (12 * 60, 13 * 60),
}

MONTH_NAME_TO_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

MONTH_DAY_PATTERN = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?$",
    re.IGNORECASE,
)

NUMERIC_DATE_PATTERN = re.compile(
    r"^(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{2,4}))?$"
)

CLOCK_TIME_PATTERN = re.compile(
    r"^(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>AM|PM)$",
    re.IGNORECASE,
)


def _dedupe_preserve_order(values: Iterable[int]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result


class SlotSuggestionService:
    def __init__(self) -> None:
        self._timezone = ZoneInfo(settings.app_timezone)
        self._max_slot_suggestions = settings.max_slot_suggestions
        self._slot_step_minutes = 15

    def suggest_slots(
        self,
        *,
        scheduling_intent: SchedulingIntentResult,
        availability: CalendarAvailabilityResult,
    ) -> SlotSuggestionResult:
        if not scheduling_intent.has_scheduling_intent:
            return SlotSuggestionResult(
                timezone=availability.timezone,
                reason="No scheduling intent detected for this email.",
            )

        duration_minutes = (
            scheduling_intent.requested_duration_minutes
            or availability.requested_duration_minutes
        )

        candidate_dates = self._resolve_candidate_dates(
            mentioned_dates=scheduling_intent.mentioned_dates,
            window_start=availability.window_start,
            window_end=availability.window_end,
        )

        if candidate_dates == set():
            return SlotSuggestionResult(
                timezone=availability.timezone,
                reason="No upcoming calendar dates matched the email's date hints.",
            )

        time_ranges = self._parse_time_ranges(
            scheduling_intent.mentioned_time_ranges
        )

        exact_times, broad_ranges = self._parse_single_time_hints(
            scheduling_intent.mentioned_times,
        )

        if time_ranges:
            exact_times = []

        suggestions: list[SuggestedMeetingSlot] = []
        seen_starts: set[datetime] = set()

        for free_window in availability.free_windows:
            window_start = self._normalize_datetime(free_window.start)
            window_end = self._normalize_datetime(free_window.end)
            window_date = window_start.date()

            if candidate_dates is not None and window_date not in candidate_dates:
                continue

            constrained_segments = self._build_constrained_segments(
                day=window_date,
                window_start=window_start,
                window_end=window_end,
                explicit_ranges=time_ranges,
                broad_ranges=broad_ranges,
            )

            if exact_times:
                for start_minutes in exact_times:
                    slot_start = self._combine_date_and_minutes(window_date, start_minutes)
                    slot_end = slot_start + timedelta(minutes=duration_minutes)

                    for segment_start, segment_end in constrained_segments:
                        if slot_start >= segment_start and slot_end <= segment_end:
                            if slot_start not in seen_starts:
                                suggestions.append(
                                    self._build_slot(
                                        start=slot_start,
                                        end=slot_end,
                                        duration_minutes=duration_minutes,
                                    )
                                )
                                seen_starts.add(slot_start)
                            break

                    if len(suggestions) >= self._max_slot_suggestions:
                        return SlotSuggestionResult(
                            timezone=availability.timezone,
                            suggestions=suggestions,
                        )
                continue

            for segment_start, segment_end in constrained_segments:
                cursor = self._round_up_to_step(segment_start, self._slot_step_minutes)

                while cursor + timedelta(minutes=duration_minutes) <= segment_end:
                    if cursor not in seen_starts:
                        slot_end = cursor + timedelta(minutes=duration_minutes)
                        suggestions.append(
                            self._build_slot(
                                start=cursor,
                                end=slot_end,
                                duration_minutes=duration_minutes,
                            )
                        )
                        seen_starts.add(cursor)

                    if len(suggestions) >= self._max_slot_suggestions:
                        return SlotSuggestionResult(
                            timezone=availability.timezone,
                            suggestions=suggestions,
                        )

                    cursor += timedelta(minutes=self._slot_step_minutes)

        if suggestions:
            return SlotSuggestionResult(
                timezone=availability.timezone,
                suggestions=suggestions,
            )

        return SlotSuggestionResult(
            timezone=availability.timezone,
            reason="No free slots matched the email's day, time, and duration hints.",
        )

    def _resolve_candidate_dates(
        self,
        *,
        mentioned_dates: list[str],
        window_start: datetime,
        window_end: datetime,
    ) -> set[date] | None:
        if not mentioned_dates:
            return None

        candidate_dates: list[date] = []
        start_date = window_start.date()
        end_date = window_end.date()

        for raw_value in mentioned_dates:
            value = raw_value.strip().casefold()

            if value in WEEKDAY_NAME_TO_INDEX:
                resolved = self._next_weekday_on_or_after(
                    start_date=start_date,
                    weekday_index=WEEKDAY_NAME_TO_INDEX[value],
                )
                if start_date <= resolved <= end_date:
                    candidate_dates.append(resolved)
                continue

            if value == "today":
                if start_date <= start_date <= end_date:
                    candidate_dates.append(start_date)
                continue

            if value == "tomorrow":
                tomorrow = start_date + timedelta(days=1)
                if start_date <= tomorrow <= end_date:
                    candidate_dates.append(tomorrow)
                continue

            if value == "this week":
                candidate_dates.extend(
                    self._dates_in_week_range(
                        anchor_date=start_date,
                        week_offset=0,
                        window_start=start_date,
                        window_end=end_date,
                    )
                )
                continue

            if value == "next week":
                candidate_dates.extend(
                    self._dates_in_week_range(
                        anchor_date=start_date,
                        week_offset=1,
                        window_start=start_date,
                        window_end=end_date,
                    )
                )
                continue

            parsed_month_day = self._parse_month_day(value, year=start_date.year)
            if parsed_month_day is not None:
                if start_date <= parsed_month_day <= end_date:
                    candidate_dates.append(parsed_month_day)
                continue

            parsed_numeric_date = self._parse_numeric_date(value, default_year=start_date.year)
            if parsed_numeric_date is not None:
                if start_date <= parsed_numeric_date <= end_date:
                    candidate_dates.append(parsed_numeric_date)
                continue

        return set(candidate_dates)

    def _parse_time_ranges(self, values: list[str]) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []

        for value in values:
            parts = [part.strip() for part in value.split("-")]
            if len(parts) != 2:
                continue

            start_minutes = self._parse_clock_minutes(parts[0])
            end_minutes = self._parse_clock_minutes(parts[1])

            if start_minutes is None or end_minutes is None:
                continue

            if end_minutes <= start_minutes:
                continue

            ranges.append((start_minutes, end_minutes))

        return ranges

    def _parse_single_time_hints(
        self,
        values: list[str],
    ) -> tuple[list[int], list[tuple[int, int]]]:
        exact_times: list[int] = []
        broad_ranges: list[tuple[int, int]] = []

        for value in values:
            normalized = value.strip().casefold()

            if normalized in PART_OF_DAY_RANGES:
                broad_ranges.append(PART_OF_DAY_RANGES[normalized])
                continue

            parsed_minutes = self._parse_clock_minutes(value)
            if parsed_minutes is not None:
                exact_times.append(parsed_minutes)

        return _dedupe_preserve_order(exact_times), broad_ranges

    def _build_constrained_segments(
        self,
        *,
        day: date,
        window_start: datetime,
        window_end: datetime,
        explicit_ranges: list[tuple[int, int]],
        broad_ranges: list[tuple[int, int]],
    ) -> list[tuple[datetime, datetime]]:
        minute_ranges = explicit_ranges or broad_ranges
        if not minute_ranges:
            return [(window_start, window_end)]

        segments: list[tuple[datetime, datetime]] = []

        for range_start, range_end in minute_ranges:
            hint_start = self._combine_date_and_minutes(day, range_start)
            hint_end = self._combine_date_and_minutes(day, range_end)

            overlap_start = max(window_start, hint_start)
            overlap_end = min(window_end, hint_end)

            if overlap_end > overlap_start:
                segments.append((overlap_start, overlap_end))

        return segments

    def _next_weekday_on_or_after(
        self,
        *,
        start_date: date,
        weekday_index: int,
    ) -> date:
        days_ahead = (weekday_index - start_date.weekday()) % 7
        return start_date + timedelta(days=days_ahead)

    def _dates_in_week_range(
        self,
        *,
        anchor_date: date,
        week_offset: int,
        window_start: date,
        window_end: date,
    ) -> list[date]:
        start_of_week = anchor_date - timedelta(days=anchor_date.weekday())
        target_week_start = start_of_week + timedelta(days=7 * week_offset)
        result: list[date] = []

        for day_offset in range(7):
            current_day = target_week_start + timedelta(days=day_offset)
            if current_day.weekday() not in settings.allowed_meeting_day_indexes:
                continue
            if window_start <= current_day <= window_end:
                result.append(current_day)

        return result

    def _parse_month_day(self, value: str, *, year: int) -> date | None:
        match = MONTH_DAY_PATTERN.match(value)
        if not match:
            return None

        month_name = match.group("month").casefold()
        day_number = int(match.group("day"))
        month_number = MONTH_NAME_TO_NUMBER.get(month_name)

        if month_number is None:
            return None

        try:
            return date(year, month_number, day_number)
        except ValueError:
            return None

    def _parse_numeric_date(self, value: str, *, default_year: int) -> date | None:
        match = NUMERIC_DATE_PATTERN.match(value)
        if not match:
            return None

        month_number = int(match.group("month"))
        day_number = int(match.group("day"))
        year_text = match.group("year")

        if year_text is None:
            year_number = default_year
        elif len(year_text) == 2:
            year_number = 2000 + int(year_text)
        else:
            year_number = int(year_text)

        try:
            return date(year_number, month_number, day_number)
        except ValueError:
            return None

    def _parse_clock_minutes(self, value: str) -> int | None:
        normalized = value.strip().upper()
        match = CLOCK_TIME_PATTERN.match(normalized)
        if not match:
            return None

        hour = int(match.group("hour"))
        minute = int(match.group("minute") or "0")
        ampm = match.group("ampm").upper()

        if hour < 1 or hour > 12:
            return None

        if minute < 0 or minute > 59:
            return None

        hour_24 = hour % 12
        if ampm == "PM":
            hour_24 += 12

        return (hour_24 * 60) + minute

    def _combine_date_and_minutes(self, day: date, minutes_since_midnight: int) -> datetime:
        midnight = datetime.combine(day, time.min, tzinfo=self._timezone)
        return midnight + timedelta(minutes=minutes_since_midnight)

    def _round_up_to_step(self, value: datetime, step_minutes: int) -> datetime:
        if value.second or value.microsecond:
            value = value.replace(second=0, microsecond=0)

        remainder = value.minute % step_minutes
        if remainder == 0:
            return value

        delta = step_minutes - remainder
        return value + timedelta(minutes=delta)

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=self._timezone)
        return value.astimezone(self._timezone)

    def _build_slot(
        self,
        *,
        start: datetime,
        end: datetime,
        duration_minutes: int,
    ) -> SuggestedMeetingSlot:
        return SuggestedMeetingSlot(
            start=start,
            end=end,
            duration_minutes=duration_minutes,
            label=self._format_slot_label(start, end),
        )

    def _format_slot_label(self, start: datetime, end: datetime) -> str:
        date_label = f"{start.strftime('%a')}, {month_abbr[start.month]} {start.day}"
        start_label = self._format_clock(start)
        end_label = self._format_clock(end)
        return f"{date_label} · {start_label} - {end_label}"

    def _format_clock(self, value: datetime) -> str:
        hour = value.hour % 12 or 12
        minute = value.minute
        ampm = "AM" if value.hour < 12 else "PM"
        return f"{hour}:{minute:02d} {ampm}"