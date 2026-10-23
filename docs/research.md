# Selection research

Research date: 2026-10-23. Public, bounded comparison; not a claim that no other similar tool exists.

### 3. Busy-only calendar export

- **Problem/users:** people sharing availability need recurring events resolved for a fixed window without disclosing subjects, descriptions, attendees, conference links, or stable original IDs.
- **Evidence:** [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545) defines calendar recurrence and free/busy information. [icalendar-anonymizer documentation](https://docs.icalendar-anonymizer.com/latest/reference/python-api.html) documents the broad set of properties that can contain private information. [Google Calendar Redactor Proxy](https://github.com/infiniteloopltd/Google-Calendar-Redactor-Proxy) is another public implementation of the sharing need.
- **Alternatives:** `icalendar-anonymizer` preserves calendar structure and recurrences while anonymizing fields; [Flatcal](https://flatcal.com/) offers extensive calendar filtering/merging; native calendar services expose availability with account sharing. These are useful alternatives, not defective products.
- **Improvement:** local CLI projects a finite date window into merged UTC Busy events built from an allowlist; no original UID, properties, alarm, recurrence rule, or extension is copied into the output. Explicit timezone for floating/all-day events, optional outward rounding and padding, refusal to overwrite.
- **Feasibility/maintenance:** use maintained iCalendar/recurrence/timezone libraries rather than inventing recurrence semantics; test DST, all-day events, exclusions/overrides, cancellation/transparency and privacy canaries. Dependency licensing and recurrence resource limits require extra review. Availability still discloses time patterns and is not anonymity.
