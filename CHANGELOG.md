# Changelog

## 0.1.0 — 2026-10-24

- Expand recurring VEVENT calendar snapshots for a finite local date window.
- Preserve recurrence exclusions/overrides and timezone/DST occupancy semantics.
- Pad, round outward, clip and merge intervals into fresh allowlisted UTC Busy events.
- Refuse scheduling messages, ambiguous floating times and occupied paths.
- Isolate recurrence expansion in a local child with a 30-second wall-time limit.

Supported scope and current limits are documented in README.md.
