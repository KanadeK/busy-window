"""Create and verify an actual privacy projection, using public synthetic data only."""

from __future__ import annotations

import json

from icalendar import Calendar

from busy_window.core import project


def main() -> None:
    raw = b"\r\n".join(
        [
            b"BEGIN:VCALENDAR",
            b"VERSION:2.0",
            b"BEGIN:VEVENT",
            b"UID:private-uid-canary",
            b"DTSTART:20261102T090000Z",
            b"DTEND:20261102T100000Z",
            b"RRULE:FREQ=DAILY;COUNT=3",
            b"EXDATE:20261103T090000Z",
            b"SUMMARY:private-title-canary",
            b"ATTENDEE:mailto:private-person@example.invalid",
            b"END:VEVENT",
            b"END:VCALENDAR",
            b"",
        ]
    )
    output, report = project(raw, "2026-11-02", "2026-11-06", "UTC")
    events = Calendar.from_ical(output).walk("VEVENT")
    assert len(events) == 2
    assert report["busy_seconds"] == 7200
    assert b"private-" not in output
    assert all(str(event["SUMMARY"]) == "Busy" for event in events)
    print(
        json.dumps(
            {
                "expanded_busy_blocks": len(events),
                "private_canaries_removed": True,
                "busy_seconds": report["busy_seconds"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
