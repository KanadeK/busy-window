# Projection contract

The date range is half open: local start midnight is included; local end midnight is excluded.
It is converted to UTC once, using the explicitly selected IANA timezone. A vendor X-WR-TIMEZONE
extension is ignored for floating dates; provided VTIMEZONE definitions remain available for
explicitly zoned events. Floating DTSTART/DTEND/RECURRENCE-ID and RDATE/EXDATE timestamps are
localized before recurrence expansion. Floating UNTIL values follow that same zone.

The recurrence engine retains series exceptions and cancelled overrides while deciding which
instances exist. Projection then ignores CANCELLED or TRANSPARENT instances. It includes tentative
and ordinary opaque events. Timed events without an end occupy zero time; all-day events without
an end occupy one local day. A negative duration or both DTEND and DURATION is an error.

Intervals receive optional symmetric padding, then outward UTC-grid rounding, then clipping to
the window. The query also includes a margin outside the requested window, so padding/rounding
of an event immediately outside it can correctly contribute busy time inside it. Sorting and
merging occur after clipping. Touching intervals merge. This intentionally hides the original
event count, gaps, recurrence pattern and boundaries within each merged block.

Output property allowlist:

- VCALENDAR: VERSION, PRODID (fixed product identifier), CALSCALE.
- VEVENT: new random UID, current export DTSTAMP, UTC DTSTART/DTEND, fixed SUMMARY:Busy,
  fixed TRANSP:OPAQUE. No nested components.

No original property value is used except the derived start/end instants. Output ends with CRLF
and is valid UTF-8 (ASCII subset). Reports contain the export window, counts, total busy seconds
and numeric options; they do not contain original event values or input paths.

The CLI runs the recurrence core in a separate Python process using binary stdin and pipes,
never a shell. A hard timeout terminates that child before any output file is created. Library
callers of `project()` get only cooperative timing, so use the CLI or their own process isolation
for potentially pathological rules. No claim of OS-level memory isolation is made.
