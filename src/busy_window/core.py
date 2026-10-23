from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import recurring_ical_events
from icalendar import Calendar

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_COMPONENTS = 10000
MAX_OCCURRENCES = 10000


class CalendarError(ValueError):
    """An expected error whose code never includes calendar property values."""


def localize(value: datetime, zone: ZoneInfo) -> datetime:
    """Resolve floating times explicitly; reject nonexistent/ambiguous floating wall times."""
    if value.tzinfo is not None:
        result = value
    else:
        result = value.replace(tzinfo=zone)
        alternative = value.replace(tzinfo=zone, fold=1)
        if result.utcoffset() != alternative.utcoffset():
            raise CalendarError("ambiguous_or_nonexistent_floating_time")
    round_trip = result.astimezone(UTC).astimezone(result.tzinfo)
    if round_trip.replace(tzinfo=None) != result.replace(tzinfo=None):
        raise CalendarError("nonexistent_local_time")
    return result


def as_utc(value: date | datetime, zone: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        return localize(value, zone).astimezone(UTC)
    if isinstance(value, date):
        return localize(datetime.combine(value, day_time()), zone).astimezone(UTC)
    raise CalendarError("invalid_event_time")


def _prepare_calendar(raw: bytes, zone: ZoneInfo) -> Calendar:
    if len(raw) > MAX_INPUT_BYTES:
        raise CalendarError("input_size_limit")
    try:
        raw.decode("utf-8-sig")
        calendar = Calendar.from_ical(raw.removeprefix(b"\xef\xbb\xbf"))
    except (ValueError, UnicodeError) as exc:
        raise CalendarError("invalid_calendar") from exc
    if calendar.name != "VCALENDAR" or str(calendar.get("VERSION", "")) != "2.0":
        raise CalendarError("unsupported_calendar")
    if str(calendar.get("METHOD", "")).upper() not in ("", "PUBLISH"):
        raise CalendarError("scheduling_message_not_calendar_snapshot")
    components = calendar.walk()
    if len(components) > MAX_COMPONENTS:
        raise CalendarError("component_count_limit")
    if any(component.errors for component in components):
        raise CalendarError("invalid_calendar_property")
    # The explicit CLI timezone, not a vendor extension, controls floating/all-day events.
    calendar.pop("X-WR-TIMEZONE", None)
    identities = set()
    for event in calendar.walk("VEVENT"):
        uid = event.get("UID")
        if not uid or isinstance(uid, list):
            raise CalendarError("missing_event_uid")
        identity = (str(uid), str(event.get("RECURRENCE-ID", "")))
        if identity in identities:
            raise CalendarError("duplicate_event_identity")
        identities.add(identity)
        if event.get("DTEND") is not None and event.get("DURATION") is not None:
            raise CalendarError("conflicting_event_duration")
        if event.get("DTSTART") is None:
            raise CalendarError("missing_event_start")
        floating_start = False
        for name in ("DTSTART", "DTEND", "RECURRENCE-ID"):
            prop = event.get(name)
            if prop is None:
                continue
            if isinstance(prop, list) or not hasattr(prop, "dt"):
                raise CalendarError("invalid_event_time")
            value = prop.dt
            if prop.params.get("TZID") and isinstance(value, datetime) and value.tzinfo is None:
                raise CalendarError("unresolved_timezone")
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    floating_start |= name == "DTSTART"
                prop.dt = localize(value, zone)
            elif not isinstance(value, date):
                raise CalendarError("invalid_event_time")
        for name in ("RDATE", "EXDATE"):
            values = event.get(name, [])
            for values_list in values if isinstance(values, list) else [values]:
                for item in values_list.dts:
                    if isinstance(item.dt, tuple):
                        raise CalendarError("period_rdate_not_supported")
                    if isinstance(item.dt, datetime):
                        if (
                            item.params.get("TZID") or values_list.params.get("TZID")
                        ) and item.dt.tzinfo is None:
                            raise CalendarError("unresolved_timezone")
                        item.dt = localize(item.dt, zone)
        rules = event.get("RRULE", [])
        for rule in rules if isinstance(rules, list) else [rules]:
            if floating_start and "UNTIL" in rule:
                rule["UNTIL"] = [
                    localize(value, zone).astimezone(UTC)
                    if isinstance(value, datetime) and value.tzinfo is None
                    else value
                    for value in rule["UNTIL"]
                ]
        start = as_utc(event["DTSTART"].dt, zone)
        if event.get("DTEND") is not None and as_utc(event["DTEND"].dt, zone) < start:
            raise CalendarError("negative_event_duration")
        if event.get("DURATION") is not None and event["DURATION"].dt < timedelta():
            raise CalendarError("negative_event_duration")
    return calendar


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged = []
    for start, stop in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(stop, merged[-1][1]))
        else:
            merged.append((start, stop))
    return merged


def _round_out(value: datetime, minutes: int, *, up: bool) -> datetime:
    if not minutes:
        return value
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    seconds = int((value - epoch).total_seconds())
    step = minutes * 60
    rounded = -(-seconds // step) * step if up else seconds // step * step
    return epoch + timedelta(seconds=rounded)


def project(
    raw: bytes,
    start_date: str,
    end_date: str,
    timezone: str,
    *,
    pad_minutes: int = 0,
    round_minutes: int = 0,
    max_occurrences: int = MAX_OCCURRENCES,
    timeout_seconds: float = 25.0,
) -> tuple[bytes, dict]:
    """Project [local start midnight, local end midnight) into fresh UTC Busy events."""
    try:
        zone = ZoneInfo(timezone)
        first, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise CalendarError("invalid_window_or_timezone") from exc
    if not 1 <= (last - first).days <= 366:
        raise CalendarError("window_must_be_1_to_366_days")
    if any(
        type(value) is not int or not 0 <= value <= 1440 for value in (pad_minutes, round_minutes)
    ):
        raise CalendarError("invalid_padding_or_rounding")
    if type(max_occurrences) is not int or not 1 <= max_occurrences <= MAX_OCCURRENCES:
        raise CalendarError("invalid_occurrence_limit")
    start, stop = as_utc(first, zone), as_utc(last, zone)
    deadline = time.monotonic() + timeout_seconds
    calendar = _prepare_calendar(raw, zone)
    margin = timedelta(minutes=pad_minutes + round_minutes)
    pad = timedelta(minutes=pad_minutes)
    intervals = []
    examined = ignored = 0
    try:
        pages = recurring_ical_events.of(calendar, skip_bad_series=False).paginate(
            128, earliest_end=start - margin, latest_start=stop + margin
        )
        for page in pages:
            for event in page:
                if time.monotonic() > deadline:
                    raise CalendarError("recurrence_time_budget")
                examined += 1
                if examined > max_occurrences:
                    raise CalendarError("occurrence_count_limit")
                if (
                    str(event.get("STATUS", "")).upper() == "CANCELLED"
                    or str(event.get("TRANSP", "")).upper() == "TRANSPARENT"
                ):
                    ignored += 1
                    continue
                begin = as_utc(event["DTSTART"].dt, zone)
                end = as_utc(event["DTEND"].dt, zone)
                if end < begin:
                    raise CalendarError("negative_event_duration")
                if end == begin:
                    ignored += 1
                    continue
                begin = max(start, _round_out(begin - pad, round_minutes, up=False))
                end = min(stop, _round_out(end + pad, round_minutes, up=True))
                if begin < end:
                    intervals.append((begin, end))
    except CalendarError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise CalendarError("invalid_or_unsupported_recurrence") from exc
    merged = merge_intervals(intervals)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//busy-window//EN", "CALSCALE:GREGORIAN"]
    for begin, end in merged:
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uuid.uuid4().hex}@busy-window.invalid",
                f"DTSTAMP:{stamp}",
                "DTSTART:" + begin.strftime("%Y%m%dT%H%M%SZ"),
                "DTEND:" + end.strftime("%Y%m%dT%H%M%SZ"),
                "SUMMARY:Busy",
                "TRANSP:OPAQUE",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    output = ("\r\n".join(lines) + "\r\n").encode("ascii")
    report = {
        "schema": "busy-window/v1",
        "window_start_utc": start.isoformat(),
        "window_end_utc": stop.isoformat(),
        "occurrences_examined": examined,
        "ignored_cancelled_transparent_or_zero": ignored,
        "busy_blocks": len(merged),
        "busy_seconds": int(sum((end - begin).total_seconds() for begin, end in merged)),
        "padding_minutes": pad_minutes,
        "rounding_minutes": round_minutes,
    }
    return output, report
