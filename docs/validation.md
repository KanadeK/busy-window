# Local validation record

Run dates: 2026-10-23–24 (Asia/Shanghai). Environment: Windows, Python 3.13.16. Version: 0.1.0 release candidate; public publication has not occurred.

- Unit/integration suite: **41 tests passed**.
- Combined statement/branch coverage: **94.3%**.
- Ruff check and format check passed.
- Bandit: no medium/high findings.
- Wheel and source distribution built successfully with setuptools 84.2.1.
- Built wheel installed in a brand-new virtual environment; version and actual demo ran; uninstall and import-absence verification passed.

Commands are in CONTRIBUTING.md and scripts/verify_install.py. Tests use synthetic data, not user files. CI is configured for Linux/Windows/macOS and Python 3.11/3.13, but those remote matrix jobs have **not run** because GitHub publication is blocked by local authentication. Local results do not establish other-platform compatibility.

Direct runtime/build requirements and the complete resolved local quality environment were checked with pip-audit 2.10.1; final scans found no known vulnerabilities. The prior setuptools 80.9.0 pin hit GHSA-h35f-9h28-mq5c and was replaced before shipping. Vulnerability databases change; this is a dated result, not a permanent guarantee.

Extra review: a real pathological secondly recurrence from 1900 was terminated by the CLI after about 30 seconds, returning worker_time_limit with no partial output. Two low-severity Bandit notices concern subprocess import/invocation; the command is a list headed by the current Python executable, invokes only the fixed local worker module, uses no shell, and is the tested recurrence time-isolation mechanism.
