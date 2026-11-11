# Decisions

| # | Decision | Reason | Options rejected |
|---|---|---|---|
| D1 | Portfolio first, continuation conditional on thresholds | A threshold fixed before the test shows a product approach | Portfolio only; real product from the start |
| D2 | Thresholds of 10 % human responses and 3 % positive responses | Above a generic mail, with enough volume to conclude | 5 %; 15 % |
| D3 | Requests limited to internship or part-time | A precise request makes the test comparable | Internship only; any type of request |
| D4 | One or two concrete examples written by the student | The only part that tells one student from another, without AI | Structured fields only; one example per role |
| D5 | 3 mails per company over 30 days, counted at generation | Protects the founder; the app always sees the generation | No limit; counter without blocking; counting at declared send |
| D6 | "Copy" buttons, limit of 5 pending mails | Matches real usage; pushes students to keep tracking up to date | `mailto:` button; hidden blind copy address |
| D7 | Named address only if published | Every address has a verifiable source; no bounces | Generic always; guessed address |
| D8 | Scraper thresholds at 70 % and 40 % | Checkpoint before investing in phases 3 to 5 | 50 %; 85 % |
| D9 | FastAPI for generation, GitHub Actions for the nightly job | Python must run on click; the nightly job needs no server | Queue in the database; templates rewritten in JavaScript |
| D10 | Mails presumed sent are excluded from the rates | It is unknown whether they left; they would distort the metric | Counting them as sent |
| D11 | Sign-up with an invitation code, no domain check | Simpler, no dependency on university mailboxes, control over who joins | Mandatory HSG address; open sign-up |
| D12 | Several template styles, style stored with each mail | The student picks the tone; the test compares styles | A single template |
| D13 | Public repository documents in English (README, PRD, DECISIONS, CHANGELOG, CLAUDE.md, code and commits) | Readable by European tech recruiters | French |
| D14 | Package `src/kaltstart/` instead of `src/ingestion/` directly | A single package name avoids import conflicts | One top-level package per component |
| D15 | Nightly synchronisation through `/changes` | It is the mechanism the API provides for synchronisation, and it also reports deletions | Re-reading `/rounds` every night |
| D16 | The sync watermark counts only successful `backfill` and `sync` runs; interrupted runs are recorded as failed | A successful details or reclean run must not hide a failed sync | Latest successful run of any command; interrupted runs left unrecorded |
| D17 | The details fetch stops and fails after 3 consecutive failures | Do not hammer a failing API; make systemic failure visible | Continue through every company; stop at the first failure |
| D18 | A repeated pagination cursor or an incomplete removed list is an error | A visible failure is better than silent data loss | Stop silently and record success |
