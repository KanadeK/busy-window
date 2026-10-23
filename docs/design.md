# Requirements and design

## User and core scenario

People sharing calendar availability need a finite Busy-only export that does not copy meeting fields.

## Architecture

Bounded local input → explicit timezone normalization → maintained recurrence engine in a time-limited child process → padding/rounding/clipping → interval union → fresh allowlisted UTC events.

## Acceptance criteria

- Recurrence EXDATE/RDATE, moved/cancelled overrides and explicit zones preserve actual occupancy.
- All-day DST days yield 23/25 hours; floating timezone ambiguity fails explicitly.
- Only derived instants and fixed/new fields occur in output, including no original IDs.
- Errors/timeouts do not create partial calendars; occupied output paths are refused.

## Scope and maintenance

Python with pinned icalendar, recurring-ical-events and timezone dependencies. The application is MIT; separate LGPL dependencies retain notices and replaceability. Only VEVENT calendar snapshots, no scheduling messages or RDATE PERIOD. Busy patterns are still identifying.

No server, database service, paid API, account credential or telemetry is required. CI only verifies/builds; it does not create source commits. See README for actual commands.
