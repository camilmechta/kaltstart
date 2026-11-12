# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

- The nightly sync no longer crashes on a round that Tech.eu has not completed
  yet (missing date, identifier, company or page link); such rounds are
  skipped and listed in the run summary.

## Phase 0 - 2026-11-11

### Added

- Design specification, validated.
- Public documents: README, PRD, DECISIONS, CHANGELOG, CLAUDE.md.
- Implementation plan for Phase 1 (ingestion).
