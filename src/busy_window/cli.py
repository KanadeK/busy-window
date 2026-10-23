from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .core import MAX_INPUT_BYTES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export only merged Busy intervals from a local ICS"
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--from", dest="start", required=True, help="Local start date, inclusive")
    parser.add_argument("--to", dest="end", required=True, help="Local end date, exclusive")
    parser.add_argument(
        "--timezone", required=True, help="IANA zone for window/floating/all-day times"
    )
    parser.add_argument("--output", type=Path, required=True, help="A NEW .ics output file")
    parser.add_argument("--pad-minutes", type=int, default=0)
    parser.add_argument("--round-minutes", type=int, default=0)
    parser.add_argument("--max-occurrences", type=int, default=10000)
    args = parser.parse_args(argv)
    created = complete = False
    try:
        if args.output.exists() or args.output.is_symlink():
            print('{"error": "output_already_exists"}', file=sys.stderr)
            return 2
        with args.input.open("rb") as source:
            raw = source.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            print('{"error": "input_size_limit"}', file=sys.stderr)
            return 2
        command = [
            sys.executable,
            "-m",
            "busy_window.worker",
            "--from",
            args.start,
            "--to",
            args.end,
            "--timezone",
            args.timezone,
            "--pad-minutes",
            str(args.pad_minutes),
            "--round-minutes",
            str(args.round_minutes),
            "--max-occurrences",
            str(args.max_occurrences),
        ]
        result = subprocess.run(command, input=raw, capture_output=True, timeout=30, check=False)
        try:
            report = json.loads(result.stderr)
            if not isinstance(report, dict):
                raise ValueError("invalid report type")
        except (ValueError, UnicodeError):
            print('{"error": "worker_protocol_error"}', file=sys.stderr)
            return 2
        if result.returncode != 0:
            error = report.get("error", "calendar_processing_error")
            # Child error codes are fixed strings; never forward calendar values or tracebacks.
            if (
                not isinstance(error, str)
                or not error.replace("_", "").isalnum()
                or len(error) > 80
            ):
                error = "calendar_processing_error"
            print(json.dumps({"error": error}), file=sys.stderr)
            return 2
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(result.stdout)
        complete = True
        print(json.dumps(report, sort_keys=True))
        return 0
    except subprocess.TimeoutExpired:
        print('{"error": "worker_time_limit"}', file=sys.stderr)
        return 2
    except OSError:
        print('{"error": "io_error"}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"error": "interrupted"}', file=sys.stderr)
        return 130
    finally:
        if created and not complete:
            args.output.unlink(missing_ok=True)
