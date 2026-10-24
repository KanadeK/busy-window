# busy-window

Share busy time from a local calendar export without copying its meeting details.

This CLI expands VEVENT recurrences for a finite date window, merges overlapping or adjacent busy
intervals, and writes a fresh UTC iCalendar containing only `Busy` events. Subjects, descriptions,
attendees, organizers, links, alarms, original identifiers and custom properties are never copied
into the output. It reads local `.ics` files and requires no calendar account or network service.

[中文说明](README.zh-CN.md) · [Privacy and semantics](docs/semantics.md) · [Dependencies](THIRD_PARTY.md)

## Install and run

Python 3.11+ is required. Use a virtual environment so dependencies remain easy to remove.

```console
git clone https://github.com/KanadeK/busy-window.git
cd busy-window
python -m venv .venv
```

Activate it (`.venv\Scripts\Activate.ps1` on PowerShell, `source .venv/bin/activate` on POSIX), then:

```console
python -m pip install .
busy-window --version
python scripts/demo.py
busy-window examples/source.ics --from 2026-11-02 --to 2026-11-06 --timezone Asia/Shanghai --output busy.ics
```

The output must be a new path; its parent must exist. Dates define **local midnight start, inclusive,
to local midnight end, exclusive**. The timezone controls the window and floating/all-day events.
Timed events with explicit zones retain their actual instants. Transparent and cancelled events
are ignored. Tentative events count as busy. The command prints a JSON summary with counts and
window times, without meeting text or original IDs. Exit `0` means export succeeded; `2` means
input/policy/I/O/processing error; `130` means interrupted.

To obscure exact boundaries, expand each interval before clipping and merging:

```console
busy-window private.ics --from 2026-11-01 --to 2026-11-08 --timezone Europe/London --pad-minutes 5 --round-minutes 15 --output share.ics
```

Padding applies to both ends. Rounding always expands outward on a UTC grid, so it never makes
an interval shorter. Values are integer minutes from 0 to 1,440; zero disables the option.
Output is clipped to the requested window. Inspect the resulting calendar before sharing it.

## Supported semantics

Maintained `icalendar` and `recurring-ical-events` libraries parse calendars, timezone definitions,
RRULEs, RDATE/EXDATE and recurrence overrides. All-day events use local day boundaries, including
23/25-hour DST days. Floating datetimes use the explicit timezone; ambiguous or nonexistent floating
times are rejected. Nonexistent aware times returned by a recurrence are also rejected.
Zero-duration timed events do not occupy time. Invalid or negative durations fail the export.

Only calendar snapshots with METHOD absent or PUBLISH are accepted; scheduling messages such as
REQUEST/CANCEL/REPLY are refused. Only VEVENT availability is projected. VTODO, VJOURNAL and existing VFREEBUSY components are not
converted. RDATE PERIOD values are currently refused. Every source event, including a cancelled
override, must include UID and DTSTART. Duplicate `(UID, RECURRENCE-ID)` definitions fail. Missing
or unresolved timezones and malformed recurrence series fail rather than producing a partial file.
See [the exact contract](docs/semantics.md) for details.

## Privacy boundary and limits

Output is constructed from a small property allowlist, with new random IDs every export. It is
never a filtered copy of the source calendar. No original title, property or recurrence rule is
serialized. Original IDs are not hashed into output IDs. The calendar still discloses busy time
patterns; rounding and merging do not guarantee anonymity or prevent re-identification. The
generated IDs also mean repeated imports can create duplicate Busy events: replace an earlier
import instead of repeatedly appending it.

- Input: UTF-8 `.ics`, optional BOM, at most 8 MiB and 10,000 components.
- Window: 1–366 local days.
- Occurrences: at most 10,000 examined (`--max-occurrences` may lower this).
- CLI: expansion runs in a local child process with a 30-second hard wall-time limit; the core
  also checks elapsed time between occurrences. All output is computed before the file is created.

The child process bounds runaway recurrence time; it is not a memory/privilege sandbox. Parsing
can expand input objects before the component cap is checked. Treat the local machine, Python
environment and filesystem parents as trusted. Do not process actively changing files or use the
tool as a public upload service without separate resource isolation. It does not alter your source
calendar, synchronize calendars, send invitations, or promise every vendor's malformed ICS dialect.
Runtime processing makes no network requests. Installing dependencies may access your package index.

## Alternatives and maintenance

[icalendar-anonymizer](https://docs.icalendar-anonymizer.com/) is appropriate when preserving original
calendar structure and recurring series is useful. Native free/busy sharing can avoid exports.
[Flatcal](https://flatcal.com/) provides broader calendar transformations. This project focuses on a
finite, merged, local availability projection built from an allowlist, with optional padding/rounding.

Project code is MIT. Runtime libraries include LGPL-3.0-or-later components imported as separate,
replaceable Python packages; their copyrights and licenses remain theirs. Read [THIRD_PARTY.md](THIRD_PARTY.md).
No dependency source is incorporated into this project's Git history. CI only tests/builds/checks.

Run the checks in [CONTRIBUTING.md](CONTRIBUTING.md). Tests cover recurrence exclusions/overrides,
DST, all-day/floating times, overlap merging, privacy canaries, malformed input and overwrite refusal.
Uninstall with `python -m pip uninstall busy-window`. The disposable `.venv` can be removed to clean
all installed dependencies; remove exports you no longer need. No cache or global state is created.
See [SECURITY.md](SECURITY.md) for private reporting. MIT © 2026 KanadeK.
