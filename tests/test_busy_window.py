from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from icalendar import Calendar

from busy_window.cli import main
from busy_window.core import MAX_INPUT_BYTES, CalendarError, as_utc, localize, project
from busy_window.worker import main as worker_main


def event(uid="fixture", start="20261102T090000Z", end="20261102T100000Z", extra=""):
    lines = ["BEGIN:VEVENT", "UID:" + uid, "DTSTART:" + start]
    if end:
        lines.append("DTEND:" + end)
    if extra:
        lines.append(extra)
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


def calendar(*events, extra=""):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + extra + "\r\n".join(events) + "\r\nEND:VCALENDAR\r\n"
    ).encode()


def blocks(output):
    return [
        (item["DTSTART"].dt, item["DTEND"].dt) for item in Calendar.from_ical(output).walk("VEVENT")
    ]


class ProjectionTests(unittest.TestCase):
    def run_projection(self, raw, **options):
        return project(raw, "2026-11-01", "2026-11-10", "UTC", **options)

    def test_single_event_and_fixed_output_allowlist(self):
        raw = calendar(
            event(
                extra="SUMMARY:private-canary\r\nDESCRIPTION:private-canary\r\n"
                "ATTENDEE:mailto:private-canary@example.invalid\r\n"
                "URL:https://example.invalid/private-canary\r\n"
                "X-PRIVATE:private-canary\r\nBEGIN:VALARM\r\n"
                "ACTION:DISPLAY\r\nTRIGGER:-PT5M\r\nDESCRIPTION:private-canary\r\nEND:VALARM"
            )
        )
        output, report = self.run_projection(raw)
        self.assertNotIn(b"private-canary", output)
        self.assertNotIn(b"fixture", output)
        self.assertEqual(report["busy_seconds"], 3600)
        result = Calendar.from_ical(output)
        self.assertEqual(set(result.keys()), {"VERSION", "PRODID", "CALSCALE"})
        item = result.walk("VEVENT")[0]
        self.assertEqual(
            set(item.keys()), {"UID", "DTSTAMP", "DTSTART", "DTEND", "SUMMARY", "TRANSP"}
        )
        self.assertEqual(item.subcomponents, [])
        self.assertEqual(str(item["SUMMARY"]), "Busy")
        self.assertNotIn("private-canary", json.dumps(report))
        self.assertIn(b"\r\n", output)

    def test_fresh_identifiers_on_every_export(self):
        raw = calendar(event())
        a = Calendar.from_ical(self.run_projection(raw)[0]).walk("VEVENT")[0]
        b = Calendar.from_ical(self.run_projection(raw)[0]).walk("VEVENT")[0]
        self.assertNotEqual(str(a["UID"]), str(b["UID"]))
        self.assertEqual(a["DTSTART"].dt, b["DTSTART"].dt)

    def test_daily_rrule_with_exdate_and_rdate(self):
        output, report = self.run_projection(
            calendar(
                event(
                    extra="RRULE:FREQ=DAILY;COUNT=3\r\n"
                    "EXDATE:20261103T090000Z\r\nRDATE:20261108T090000Z"
                )
            )
        )
        self.assertEqual([begin.day for begin, _ in blocks(output)], [2, 4, 8])
        self.assertEqual(report["busy_seconds"], 10800)

    def test_moved_recurrence_override(self):
        master = event(extra="RRULE:FREQ=DAILY;COUNT=3")
        override = event(
            start="20261103T130000Z", end="20261103T140000Z", extra="RECURRENCE-ID:20261103T090000Z"
        )
        output, _ = self.run_projection(calendar(master, override))
        self.assertEqual(
            [(begin.day, begin.hour) for begin, _ in blocks(output)], [(2, 9), (3, 13), (4, 9)]
        )

    def test_cancelled_recurrence_override(self):
        master = event(extra="RRULE:FREQ=DAILY;COUNT=3")
        override = event(
            start="20261103T090000Z",
            end="20261103T100000Z",
            extra="RECURRENCE-ID:20261103T090000Z\r\nSTATUS:CANCELLED",
        )
        output, _ = self.run_projection(calendar(master, override))
        self.assertEqual([begin.day for begin, _ in blocks(output)], [2, 4])

    def test_cancelled_and_transparent_events_are_excluded(self):
        output, _ = self.run_projection(
            calendar(
                event("cancelled", extra="STATUS:CANCELLED"),
                event("transparent", extra="TRANSP:TRANSPARENT"),
            )
        )
        self.assertEqual(blocks(output), [])

    def test_tentative_event_is_busy(self):
        output, _ = self.run_projection(calendar(event(extra="STATUS:TENTATIVE")))
        self.assertEqual(len(blocks(output)), 1)

    def test_floating_time_uses_explicit_timezone_over_extension(self):
        raw = calendar(
            event(start="20261102T090000", end="20261102T100000"),
            extra="X-WR-TIMEZONE:America/New_York\r\n",
        )
        output, _ = project(raw, "2026-11-01", "2026-11-04", "Asia/Shanghai")
        self.assertEqual(blocks(output)[0][0], datetime(2026, 11, 2, 1, tzinfo=UTC))

    def test_floating_until_is_localized(self):
        raw = calendar(
            event(
                start="20261102T090000",
                end="20261102T100000",
                extra="RRULE:FREQ=DAILY;UNTIL=20261103T090000",
            )
        )
        output, _ = project(raw, "2026-11-01", "2026-11-05", "Asia/Shanghai")
        self.assertEqual([begin.day for begin, _ in blocks(output)], [2, 3])

    def test_floating_exdate_is_localized(self):
        raw = calendar(
            event(
                start="20261102T090000",
                end="20261102T100000",
                extra="RRULE:FREQ=DAILY;COUNT=3\r\nEXDATE:20261103T090000",
            )
        )
        output, _ = project(raw, "2026-11-01", "2026-11-06", "Asia/Shanghai")
        self.assertEqual([begin.day for begin, _ in blocks(output)], [2, 4])

    def test_explicit_zone_recurs_across_fall_dst(self):
        raw = calendar(
            "BEGIN:VEVENT\r\nUID:dst\r\nDTSTART;TZID=America/New_York:20261031T090000\r\n"
            "DTEND;TZID=America/New_York:20261031T100000\r\nRRULE:FREQ=DAILY;COUNT=3\r\nEND:VEVENT"
        )
        output, _ = project(raw, "2026-10-31", "2026-11-03", "America/New_York")
        self.assertEqual([begin.hour for begin, _ in blocks(output)], [13, 14, 14])

    def test_all_day_fall_dst_is_25_hours(self):
        raw = calendar(
            "BEGIN:VEVENT\r\nUID:day\r\nDTSTART;VALUE=DATE:20261101\r\n"
            "DTEND;VALUE=DATE:20261102\r\nEND:VEVENT"
        )
        output, report = project(raw, "2026-11-01", "2026-11-02", "America/New_York")
        self.assertEqual(report["busy_seconds"], 25 * 3600)
        self.assertEqual((blocks(output)[0][1] - blocks(output)[0][0]).total_seconds(), 25 * 3600)

    def test_all_day_spring_dst_is_23_hours(self):
        raw = calendar(
            "BEGIN:VEVENT\r\nUID:day\r\nDTSTART;VALUE=DATE:20260308\r\n"
            "DTEND;VALUE=DATE:20260309\r\nEND:VEVENT"
        )
        _, report = project(raw, "2026-03-08", "2026-03-09", "America/New_York")
        self.assertEqual(report["busy_seconds"], 23 * 3600)

    def test_all_day_without_end_is_one_day(self):
        raw = calendar("BEGIN:VEVENT\r\nUID:day\r\nDTSTART;VALUE=DATE:20261102\r\nEND:VEVENT")
        _, report = self.run_projection(raw)
        self.assertEqual(report["busy_seconds"], 86400)

    def test_timed_without_end_is_ignored(self):
        output, _ = self.run_projection(calendar(event(end=None)))
        self.assertEqual(blocks(output), [])

    def test_overlap_and_touching_intervals_merge(self):
        raw = calendar(
            event("one"),
            event("two", "20261102T093000Z", "20261102T110000Z"),
            event("three", "20261102T110000Z", "20261102T120000Z"),
        )
        output, report = self.run_projection(raw)
        self.assertEqual(len(blocks(output)), 1)
        self.assertEqual(report["busy_seconds"], 10800)

    def test_padding_rounding_and_clipping(self):
        raw = calendar(event(start="20261102T090700Z", end="20261102T091600Z"))
        output, report = self.run_projection(raw, pad_minutes=5, round_minutes=15)
        self.assertEqual((blocks(output)[0][0].hour, blocks(output)[0][0].minute), (9, 0))
        self.assertEqual(blocks(output)[0][1].minute, 30)
        self.assertEqual(report["busy_seconds"], 1800)

    def test_padding_outside_window_is_included(self):
        raw = calendar(event(start="20261101T235500Z", end="20261101T235800Z"))
        output, report = project(raw, "2026-11-02", "2026-11-03", "UTC", pad_minutes=5)
        self.assertEqual(report["busy_seconds"], 180)
        self.assertEqual(blocks(output)[0][0], datetime(2026, 11, 2, tzinfo=UTC))

    def test_half_open_end_and_clipping(self):
        raw = calendar(
            event("cross", "20261101T233000Z", "20261102T003000Z"),
            event("at-end", "20261103T000000Z", "20261103T010000Z"),
        )
        output, report = project(raw, "2026-11-02", "2026-11-03", "UTC")
        self.assertEqual(report["busy_seconds"], 1800)
        self.assertEqual(len(blocks(output)), 1)

    def test_empty_calendar(self):
        output, report = self.run_projection(calendar())
        self.assertEqual(report["busy_blocks"], 0)
        self.assertEqual(blocks(output), [])

    def test_utf8_bom(self):
        output, _ = self.run_projection(b"\xef\xbb\xbf" + calendar(event()))
        self.assertEqual(len(blocks(output)), 1)

    def test_scheduling_messages_are_not_mistaken_for_calendar_snapshots(self):
        with self.assertRaisesRegex(CalendarError, "scheduling_message_not_calendar_snapshot"):
            self.run_projection(calendar(event(), extra="METHOD:CANCEL\r\n"))

    def test_unknown_rdate_tzid_is_not_treated_as_a_floating_time(self):
        raw = calendar(event(extra="RDATE;TZID=Unknown/Zone:20261103T090000"))
        with self.assertRaisesRegex(CalendarError, "unresolved_timezone"):
            self.run_projection(raw)

    def test_invalid_dates_windows_zones_and_policies(self):
        raw = calendar(event())
        for start, end, zone in (
            ("bad", "2026-11-03", "UTC"),
            ("2026-11-02", "2026-11-02", "UTC"),
            ("2026-11-02", "2028-11-03", "UTC"),
            ("2026-11-02", "2026-11-03", "Not/AZone"),
        ):
            with self.subTest(start=start, end=end, zone=zone), self.assertRaises(CalendarError):
                project(raw, start, end, zone)
        for options in ({"pad_minutes": -1}, {"round_minutes": 1441}, {"max_occurrences": 0}):
            with self.subTest(options=options), self.assertRaises(CalendarError):
                self.run_projection(raw, **options)

    def test_malformed_calendar_and_properties(self):
        for raw in (
            b"not a calendar",
            b"\xff",
            calendar(event()).replace(b"VERSION:2.0", b"VERSION:3.0"),
            calendar(event()).replace(b"20261102T090000Z", b"bad-time"),
        ):
            with self.subTest(raw=raw), self.assertRaises(CalendarError):
                self.run_projection(raw)

    def test_missing_uid_or_start_and_duplicate_identity(self):
        for raw in (
            calendar(event()).replace(b"UID:fixture\r\n", b""),
            calendar(event()).replace(b"DTSTART:20261102T090000Z\r\n", b""),
            calendar(event(), event()),
        ):
            with self.subTest(raw=raw), self.assertRaises(CalendarError):
                self.run_projection(raw)

    def test_negative_and_conflicting_duration(self):
        for raw in (
            calendar(event(end="20261102T080000Z")),
            calendar(event(extra="DURATION:PT1H")),
            calendar(event(end=None, extra="DURATION:-PT1H")),
        ):
            with self.subTest(raw=raw), self.assertRaises(CalendarError):
                self.run_projection(raw)

    def test_duration_property(self):
        _, report = self.run_projection(calendar(event(end=None, extra="DURATION:PT90M")))
        self.assertEqual(report["busy_seconds"], 5400)

    def test_unknown_tzid_and_period_rdate_are_refused(self):
        raw = (
            calendar(event())
            .replace(b"DTSTART:", b"DTSTART;TZID=Unknown/Zone:")
            .replace(b"20261102T090000Z", b"20261102T090000")
        )
        with self.assertRaisesRegex(CalendarError, "unresolved_timezone"):
            self.run_projection(raw)
        raw = calendar(event(extra="RDATE;VALUE=PERIOD:20261104T090000Z/20261104T100000Z"))
        with self.assertRaisesRegex(CalendarError, "period_rdate_not_supported"):
            self.run_projection(raw)

    def test_ambiguous_and_nonexistent_floating_times_are_refused(self):
        zone = ZoneInfo("America/New_York")
        for value in (datetime(2026, 11, 1, 1, 30), datetime(2026, 3, 8, 2, 30)):
            with self.subTest(value=value), self.assertRaises(CalendarError):
                localize(value, zone)
        with self.assertRaises(CalendarError):
            as_utc(datetime(2026, 3, 8, 2, 30, tzinfo=zone), zone)

    def test_invalid_as_utc_value(self):
        with self.assertRaises(CalendarError):
            as_utc("not a date", ZoneInfo("UTC"))

    def test_input_and_component_limits(self):
        with self.assertRaisesRegex(CalendarError, "input_size_limit"):
            self.run_projection(b" " * (MAX_INPUT_BYTES + 1))
        raw = calendar(*(["BEGIN:VTODO\r\nEND:VTODO"] * 10001))
        with self.assertRaisesRegex(CalendarError, "component_count_limit"):
            self.run_projection(raw)

    def test_occurrence_limit_and_cooperative_deadline(self):
        raw = calendar(event(extra="RRULE:FREQ=DAILY;COUNT=5"))
        with self.assertRaisesRegex(CalendarError, "occurrence_count_limit"):
            self.run_projection(raw, max_occurrences=2)
        with self.assertRaisesRegex(CalendarError, "recurrence_time_budget"):
            self.run_projection(raw, timeout_seconds=1e-12)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / "private.ics", self.root / "busy.ics"
        self.source.write_bytes(calendar(event(extra="SUMMARY:private-canary")))
        self.command = [
            str(self.source),
            "--from",
            "2026-11-01",
            "--to",
            "2026-11-05",
            "--timezone",
            "UTC",
            "--output",
            str(self.output),
        ]

    def test_cli_runs_actual_child_and_leaves_source_unchanged(self):
        original = self.source.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(self.command), 0)
        self.assertEqual(json.loads(output.getvalue())["busy_blocks"], 1)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertNotIn(b"private-canary", self.output.read_bytes())

    def test_cli_refuses_existing_output(self):
        self.output.write_bytes(b"keep")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(self.command), 2)
        self.assertEqual(self.output.read_bytes(), b"keep")

    def test_invalid_calendar_has_no_partial_output_or_source_values(self):
        self.source.write_bytes(b"private-invalid-canary")
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(self.command), 2)
        self.assertFalse(self.output.exists())
        self.assertNotIn("private-invalid-canary", errors.getvalue())

    def test_cli_io_and_size_errors(self):
        self.source.unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(self.command), 2)
        self.source.write_bytes(b"x" * (MAX_INPUT_BYTES + 1))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(self.command), 2)
        self.assertFalse(self.output.exists())

    def test_child_hard_timeout_has_no_output(self):
        with (
            patch(
                "busy_window.cli.subprocess.run",
                side_effect=subprocess.TimeoutExpired("worker", 30),
            ),
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            self.assertEqual(main(self.command), 2)
        self.assertIn("worker_time_limit", errors.getvalue())
        self.assertFalse(self.output.exists())

    def test_worker_protocol_failure(self):
        result = subprocess.CompletedProcess([], 1, b"", b"not json")
        with (
            patch("busy_window.cli.subprocess.run", return_value=result),
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            self.assertEqual(main(self.command), 2)
        self.assertIn("worker_protocol_error", errors.getvalue())


class WorkerTests(unittest.TestCase):
    def invoke(self, raw):
        stdin = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
        destination = io.BytesIO()
        stdout = io.TextIOWrapper(destination, encoding="utf-8")
        stderr = io.StringIO()
        with (
            patch("sys.stdin", stdin),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
            patch(
                "sys.argv",
                ["worker", "--from", "2026-11-01", "--to", "2026-11-04", "--timezone", "UTC"],
            ),
        ):
            status = worker_main()
            stdout.flush()
            result = destination.getvalue()
        return status, result, stderr.getvalue()

    def test_worker_success_and_known_error(self):
        status, output, report = self.invoke(calendar(event()))
        self.assertEqual(status, 0)
        self.assertEqual(len(blocks(output)), 1)
        self.assertEqual(json.loads(report)["busy_blocks"], 1)
        self.assertEqual(self.invoke(b"broken")[0], 2)

    def test_worker_unexpected_exception_is_redacted(self):
        with patch("busy_window.worker.project", side_effect=RuntimeError("private-canary")):
            status, output, errors = self.invoke(calendar(event()))
        self.assertEqual(status, 2)
        self.assertEqual(output, b"")
        self.assertNotIn("private-canary", errors)
        self.assertIn("calendar_processing_error", errors)


if __name__ == "__main__":
    unittest.main()
