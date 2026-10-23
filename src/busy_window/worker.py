"""A local child process so a pathological recurrence can be terminated by the CLI."""

from __future__ import annotations

import argparse
import json
import sys

from .core import MAX_INPUT_BYTES, CalendarError, project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--timezone", required=True)
    parser.add_argument("--pad-minutes", type=int, default=0)
    parser.add_argument("--round-minutes", type=int, default=0)
    parser.add_argument("--max-occurrences", type=int, default=10000)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        output, report = project(
            raw,
            args.start,
            args.end,
            args.timezone,
            pad_minutes=args.pad_minutes,
            round_minutes=args.round_minutes,
            max_occurrences=args.max_occurrences,
        )
        sys.stdout.buffer.write(output)
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 0
    except CalendarError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except Exception:
        # Parser/library exceptions must never echo private properties or partial calendars.
        print('{"error": "calendar_processing_error"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
