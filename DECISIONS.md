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
| D19 | Weekly `backfill` every Sunday, in addition to the nightly `sync` | `/changes` reports added and removed rounds only, so edits to known rounds (such as an amount published later) would never arrive; a re-read costs about ten requests | Accept stale rounds; re-read `/rounds` every night |
| D20 | The design spec and the implementation plans are in English too, extending D13 to every file in the repository | The repository is public; a reader should not hit a language switch between the code and its design documents | Keep the spec and plans in French |
| D21 | A round without a date is skipped and counted in the run summary, not stored | `/changes` can report a freshly created round before Tech.eu dates it (seen live on 2026-11-12); an undated round cannot be placed in the 12-month window and the mail quotes the date. The weekly backfill picks it up once dated | Use `createdAt` as the date; fail the run |
| D22 | Size bounds for rounds without a known stage set to 7 and 20 million euros (were 3 and 15) | Calibrated on the first load (2026-11-12, 832 rounds): median amounts are 2.0M for Pre-Seed, 4.3M for Seed, 12.0M for Series A and 31.8M for Series B, so each bound sits about halfway between the two stages it separates. With 3M, more than half of Seed-sized rounds would have been classified medium | Keep 3 and 15; fit the bounds on the full distribution |
