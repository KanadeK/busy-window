# Runtime dependency notices

The project's original application code is MIT © 2026 KanadeK. The packages below are imported
as separate Python distributions and are not vendored or copied into the application's source.
Their original copyrights, licenses and authorship are preserved. Installed dependency wheels
carry their own notices. Copies of license texts available in the inspected distributions are
also retained in `third_party_licenses/`.

| Dependency | Pinned version | License | Original source |
|---|---|---|---|
| icalendar | 7.3.0 | BSD-2-Clause | https://github.com/collective/icalendar |
| recurring-ical-events | 3.8.2 | LGPL-3.0-or-later | https://github.com/niccokunzmann/python-recurring-ical-events |
| x-wr-timezone | 2.0.1 | LGPL-3.0-or-later | https://github.com/niccokunzmann/x-wr-timezone |
| tzdata | 2026.5 | Apache-2.0; IANA data notices retained | https://github.com/python/tzdata |
| python-dateutil | 2.9.0.post0 | Apache-2.0 / BSD-3-Clause | https://github.com/dateutil/dateutil |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| click | 8.5.0 | BSD-3-Clause | https://github.com/pallets/click |
| typing-extensions (Python <3.13) | 4.15.0 | PSF-2.0 | https://github.com/python/typing_extensions |

LGPL components remain LGPL. This application imports them through ordinary, unmodified Python
interfaces; they can be replaced or modified in the virtual environment. There is no frozen
executable, signature gate or restriction on debugging/modifying those libraries. This MIT license
does not relicense the dependencies. Redistributors must preserve the relevant licenses and meet
the LGPL requirements for their distribution, including access to corresponding library source;
the upstream version tags/source archives provide that source. See the full LGPL/GPL texts in
the notices directory and [GNU LGPL v3](https://www.gnu.org/licenses/lgpl-3.0.html).

Development tools are listed separately in `requirements-dev.txt` and are not runtime dependencies.
No third-party project source or test fixtures were copied. The dependency license copies are
clearly attributed and are not claimed as original application code.
