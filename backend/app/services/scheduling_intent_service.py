from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from app.schemas import SchedulingIntentResult

SCHEDULING_KEYWORDS = (
    "schedule",
    "scheduling",
    "meeting",
    "meet",
    "call",
    "phone call",
    "video call",
    "zoom",
    "google meet",
    "teams",
    "availability",
    "available",
    "calendar",
    "invite",
    "reschedule",
    "connect",
    "sync",
    "check-in",
    "catch up",
    "what time works",
    "when works for you",
    "does this work for you",
)

STRONG_SCHEDULING_PHRASES = (
    "are you available",
    "what time works",
    "when works for you",
    "does this work for you",
    "can we meet",
    "can we schedule",
    "would you be available",
    "let's meet",
    "please share your availability",
    "please send your availability",
)

PROMOTIONAL_KEYWORDS = (
    "unsubscribe",
    "view in browser",
    "newsletter",
    "special offer",
    "sale",
    "promo",
    "register now",
    "limited time",
)

DATE_PATTERNS = (
    re.compile(
        r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:today|tomorrow|tonight|this week|next week|this month|next month)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
        r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b"),
)

TIMEZONE_PATTERN = re.compile(
    r"\b(?:UTC|GMT|BST|CET|CEST|EET|IST|JST|AEST|AEDT|PST|PDT|MST|MDT|CST|CDT|EST|EDT|ET|CT|MT|PT)\b",
    re.IGNORECASE,
)

DURATION_PATTERN = re.compile(
    r"\b(?P<value>\d{1,3})\s*(?P<unit>minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)

SINGLE_TIME_PATTERN = re.compile(
    r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)\b",
    re.IGNORECASE,
)

PART_OF_DAY_PATTERN = re.compile(
    r"\b(?:morning|afternoon|evening|noon)\b",
    re.IGNORECASE,
)

TIME_RANGE_PATTERNS = (
    re.compile(
        r"\bbetween\s+(?:like\s+)?"
        r"(?P<start_hour>\d{1,2})(?::(?P<start_minute>\d{2}))?\s*(?P<start_ampm>am|pm)?"
        r"\s*(?:-|to|and|or)\s*"
        r"(?P<end_hour>\d{1,2})(?::(?P<end_minute>\d{2}))?\s*(?P<end_ampm>am|pm)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bfrom\s+"
        r"(?P<start_hour>\d{1,2})(?::(?P<start_minute>\d{2}))?\s*(?P<start_ampm>am|pm)?"
        r"\s*(?:-|to|and|or)\s*"
        r"(?P<end_hour>\d{1,2})(?::(?P<end_minute>\d{2}))?\s*(?P<end_ampm>am|pm)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<start_hour>\d{1,2})(?::(?P<start_minute>\d{2}))?\s*(?P<start_ampm>am|pm)?"
        r"\s*(?:-|to|and|or)\s*"
        r"(?P<end_hour>\d{1,2})(?::(?P<end_minute>\d{2}))?\s*(?P<end_ampm>am|pm)\b",
        re.IGNORECASE,
    ),
)

QUOTED_HEADER_PATTERNS = (
    re.compile(r"^on .+ wrote:\s*$", re.IGNORECASE),
    re.compile(r"^(from|sent|to|subject|date|cc):\s*", re.IGNORECASE),
)

BODY_FIELDS = ("subject", "body_text", "body", "plain_text", "text", "snippet")


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue

        key = cleaned.casefold()
        if key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _normalize_clock_time(hour_text: str, minute_text: str | None, ampm_text: str) -> str | None:
    try:
        hour = int(hour_text)
    except ValueError:
        return None

    if hour < 1 or hour > 12:
        return None

    minute = (minute_text or "").strip()
    ampm = ampm_text.strip().upper()

    if minute and minute != "00":
        return f"{hour}:{minute} {ampm}"

    return f"{hour} {ampm}"


def _span_overlaps(span: tuple[int, int], blocked_spans: list[tuple[int, int]]) -> bool:
    start, end = span

    for blocked_start, blocked_end in blocked_spans:
        if start < blocked_end and end > blocked_start:
            return True

    return False


class SchedulingIntentService:
    def analyze_message(self, message: Mapping[str, Any]) -> SchedulingIntentResult:
        text_blob = self._build_text_blob(message)
        lowered = text_blob.casefold()

        keyword_hits = sum(1 for keyword in SCHEDULING_KEYWORDS if keyword in lowered)
        strong_phrase_hits = sum(1 for phrase in STRONG_SCHEDULING_PHRASES if phrase in lowered)
        promotional_hits = sum(1 for keyword in PROMOTIONAL_KEYWORDS if keyword in lowered)

        mentioned_dates = self._extract_dates(text_blob)
        mentioned_time_ranges, range_times, range_spans = self._extract_time_ranges(text_blob)
        single_times = self._extract_single_times(text_blob, exclude_spans=range_spans)
        part_of_day_times = self._extract_part_of_day_times(text_blob)

        mentioned_times = _dedupe_preserve_order(
            [*range_times, *single_times, *part_of_day_times]
        )
        timezone_clues = self._extract_timezones(text_blob)
        requested_duration_minutes = self._extract_duration_minutes(text_blob)

        score = 0.0

        if strong_phrase_hits:
            score += 0.45

        if keyword_hits >= 2:
            score += 0.35
        elif keyword_hits == 1:
            score += 0.20

        if mentioned_dates:
            score += 0.15

        if mentioned_time_ranges:
            score += 0.20
        elif mentioned_times:
            score += 0.15

        if requested_duration_minutes is not None:
            score += 0.10

        if timezone_clues:
            score += 0.05

        if promotional_hits and keyword_hits == 0 and strong_phrase_hits == 0:
            score -= 0.35
        elif promotional_hits >= 2:
            score -= 0.15

        has_scheduling_intent = score >= 0.45 or (
            (keyword_hits > 0 or strong_phrase_hits > 0)
            and (bool(mentioned_dates) or bool(mentioned_times) or bool(mentioned_time_ranges))
        )

        notes: str | None = None
        if has_scheduling_intent and not mentioned_dates and not mentioned_times and not mentioned_time_ranges:
            notes = "Scheduling language detected, but no specific date or time was extracted."
        elif not has_scheduling_intent and keyword_hits > 0:
            notes = "Scheduling language was weak or ambiguous."

        return SchedulingIntentResult(
            has_scheduling_intent=has_scheduling_intent,
            confidence=_clamp(score),
            requested_duration_minutes=requested_duration_minutes,
            mentioned_dates=mentioned_dates,
            mentioned_times=mentioned_times,
            mentioned_time_ranges=mentioned_time_ranges,
            timezone_clues=timezone_clues,
            notes=notes,
        )

    def _build_text_blob(self, message: Mapping[str, Any]) -> str:
        parts: list[str] = []

        for field_name in BODY_FIELDS:
            value = message.get(field_name)
            if value:
                parts.append(str(value))

        combined = "\n".join(part.strip() for part in parts if part and str(part).strip())
        cleaned = self._remove_quoted_headers(combined)
        return cleaned[:6000]

    def _remove_quoted_headers(self, text: str) -> str:
        kept_lines: list[str] = []

        for raw_line in text.splitlines():
            stripped = raw_line.strip()

            if not stripped:
                kept_lines.append("")
                continue

            if stripped.startswith(">"):
                continue

            if any(pattern.match(stripped) for pattern in QUOTED_HEADER_PATTERNS):
                continue

            kept_lines.append(raw_line)

        return "\n".join(kept_lines)

    def _extract_dates(self, text: str) -> list[str]:
        matches: list[str] = []

        for pattern in DATE_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0).strip()
                if value:
                    matches.append(value)

        return _dedupe_preserve_order(matches)

    def _extract_time_ranges(self, text: str) -> tuple[list[str], list[str], list[tuple[int, int]]]:
        ranges: list[str] = []
        points: list[str] = []
        spans: list[tuple[int, int]] = []

        for pattern in TIME_RANGE_PATTERNS:
            for match in pattern.finditer(text):
                start_ampm = match.group("start_ampm") or match.group("end_ampm")
                end_ampm = match.group("end_ampm")

                if not start_ampm or not end_ampm:
                    continue

                start_time = _normalize_clock_time(
                    hour_text=match.group("start_hour"),
                    minute_text=match.group("start_minute"),
                    ampm_text=start_ampm,
                )
                end_time = _normalize_clock_time(
                    hour_text=match.group("end_hour"),
                    minute_text=match.group("end_minute"),
                    ampm_text=end_ampm,
                )

                if not start_time or not end_time:
                    continue

                ranges.append(f"{start_time} - {end_time}")
                points.extend([start_time, end_time])
                spans.append(match.span())

        return (
            _dedupe_preserve_order(ranges),
            _dedupe_preserve_order(points),
            spans,
        )

    def _extract_single_times(
        self,
        text: str,
        *,
        exclude_spans: list[tuple[int, int]],
    ) -> list[str]:
        matches: list[str] = []

        for match in SINGLE_TIME_PATTERN.finditer(text):
            if _span_overlaps(match.span(), exclude_spans):
                continue

            normalized = _normalize_clock_time(
                hour_text=match.group("hour"),
                minute_text=match.group("minute"),
                ampm_text=match.group("ampm"),
            )
            if normalized:
                matches.append(normalized)

        return _dedupe_preserve_order(matches)

    def _extract_part_of_day_times(self, text: str) -> list[str]:
        return _dedupe_preserve_order(
            match.group(0).strip() for match in PART_OF_DAY_PATTERN.finditer(text)
        )

    def _extract_timezones(self, text: str) -> list[str]:
        return _dedupe_preserve_order(
            match.group(0).upper() for match in TIMEZONE_PATTERN.finditer(text)
        )

    def _extract_duration_minutes(self, text: str) -> int | None:
        match = DURATION_PATTERN.search(text)
        if not match:
            return None

        value = int(match.group("value"))
        unit = match.group("unit").casefold()

        if "hour" in unit or "hr" in unit:
            return value * 60

        return value