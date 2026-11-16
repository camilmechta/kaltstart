# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Mail generator (`kaltstart.mailgen`): three styles in English and German,
  an optional sentence of the student about the company, refusal naming any
  missing data, and every combination tested at its longest.
- Austria is read every night after Switzerland and Germany. Pages up to
  5 MB are read (2 MB before), so heavy home pages are no longer counted as
  unreachable.
- First measurement in Austria, on 20 companies: address found for 15 of the
  18 that publish one, no wrong address, people accuracy 9 lists of 10.
- Germany is read every night after Switzerland; `run` and `status` take
  several `--country` options.
- First measurement in Germany, on 20 companies: address found for 18 of the
  18 that publish one, people accuracy 10 lists of 13, coverage 50 %.
- Migration `0003`: removal of a person also covers their addresses
  whatever their type, name keys are computed alike in Python and SQL,
  `exclude_person` reports what it removed, and each run counts its
  database write errors.
- First full contact run on the 236 eligible Swiss companies: 161 with an
  address stored, 110 with a person suggested. The nightly run is live.
- Contact storage: tables `contact_emails`, `contact_people`,
  `contact_exclusions` and `contact_runs`, the `run` and `status` commands,
  and the `contacts` workflow that reads the due company sites every night
  (Switzerland only for now). Removal on request through two SQL functions.
- Contact scraper (`kaltstart.contacts`): polite fetcher, page choice, address
  and founder extraction, contact selection, and the `measure` and `summary`
  commands. Not run nightly and not connected to the database yet.
- `sample` command to draw companies for a measurement, and a free-text
  `args` input on the manual workflow run.
- First measurement on 20 Swiss companies: usable address confirmed for 65 %
  (inconclusive against 70 %), founder name confirmed for 5 % (fails 40 %).
- Second measurement on 20 new companies after the founder rewrite: usable
  address 65 %, founder name 30 %. Both thresholds still missed.
- Third measurement on 20 new companies: usable address 70 %, founder name
  45 %, both above their thresholds by one company (inconclusive).
- Fourth measurement with the same code, and verdict on 40 companies: usable
  address 70 % (pass), founder name 35 % (fail).
- Fifth to seventh measurements, on 60 new companies with the people
  scraper: people accuracy 24 lists of 25 (96 %, pass), people coverage 40 %
  (at the goal), usable address 52 % (fail against 65 %).
- Eighth measurement, on 20 new companies after the address fixes: usable
  address 70 % (one company above 65 %, inconclusive), people accuracy 8
  lists of 10, people coverage 40 %. No wrong address.

### Changed

- The contact scraper reads people with their job title instead of founders
  only, keeps leaders, function heads and managers, and recruiters, and
  proposes the person matching the student's target role. Two criteria
  replace the founder threshold: accuracy (90 %, blocking) and coverage
  (40 %, a goal).
- After a tuning run on the 80 companies already measured: titles written
  above the name, titles followed by a biography in the same block and names
  three levels above the title are read; text a page never shows, cards with
  a customer's logo and job titles in Italian or French are not. A website
  that is a profile on another organisation's site is reported as
  `not_own_site` and not read.
- A person read by the scraper is now a suggestion the student confirms on
  its source page; people accuracy (90 %) is tracked and no longer blocks.
- A caption that introduces somebody ("With ...") is not read as a name, and
  "Personal Care" in a title is no longer read as human resources.
- People under a plain "Board" or "Advisors" label, and people on a card
  that links to a customer story, are no longer kept.
- Ninth measurement, on 20 new companies: address found for 13 of the 16
  companies that publish one, no wrong address, people accuracy 6 lists of
  9 (fail), people coverage 30 %.
- The address threshold (65 % of all companies) is replaced by two criteria:
  an address found for 75 % of the companies that publish one on a site of
  their own, and no wrong address. The `summary` command reports both.
- After the verdict on 60 companies, three address fixes: the root of the
  site is read when the stored page no longer exists, a "Site Notice" link
  is read as a legal notice, and an address on a second domain that carries
  the company's name is kept.
- A network failure on `robots.txt` is reported as `unreachable`, not as
  `robots_forbidden`.
- Founder extraction rewritten from the failures of the first measurement:
  names are read only from team cards, "Name, role" lines and legal-notice
  labels, and only when the role is held at the company itself.
- After the second measurement: names one or two levels above the role are
  read, customer testimonials are skipped, Cloudflare-protected addresses are
  decoded. The usable-contact threshold is lowered from 70 % to 65 %.

## Phase 1 - 2026-11-12

First load run against the live database on 2026-11-11: 832 funding rounds
(Germany 508, Switzerland 260, Austria 64), 783 companies, 780 of them with a
website.

### Added

- Python package `kaltstart`, test setup with pytest, CI workflow, recorded
  Tech.eu API fixtures for tests.
- Ingestion: cleaning and transform functions, Tech.eu HTTP client, store
  interface with in-memory and Supabase implementations, SQL schema, pipelines
  (backfill, sync, details, reclean), command line interface.
- Nightly GitHub Actions workflow for `sync`, weekly `backfill` (Sundays) to
  pick up edits to known rounds, which the `/changes` endpoint does not
  report, and manual runs of any command including `report` and `cities`.
- `report` prints the share of companies with fetched details and with a
  website.

### Changed

- Size bounds for rounds without a known stage calibrated on real data:
  7 and 20 million euros (were 3 and 15).
- City aliases completed from the first load: spelling variants, one
  encoding glitch, and regions that Tech.eu stores in the city field.
- Design spec and Phase 1 plan translated to English; the spec file is now
  `docs/superpowers/specs/2026-11-11-kaltstart-design.md`.

### Fixed

- An address whose first letters a page writes outside its mail link is no
  longer stored as a second, truncated address.
- The nightly sync no longer crashes on a round that Tech.eu has not completed
  yet (missing date, identifier, company or page link); such rounds are
  skipped and listed in the run summary.

## Phase 0 - 2026-11-11

### Added

- Design specification, validated.
- Public documents: README, PRD, DECISIONS, CHANGELOG, CLAUDE.md.
- Implementation plan for Phase 1 (ingestion).
