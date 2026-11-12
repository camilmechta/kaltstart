# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Project scaffold: Python package `kaltstart`, test setup with pytest, CI
  workflow, recorded Tech.eu API fixtures for tests.
- Phase 1 ingestion code: cleaning and transform functions, Tech.eu HTTP
  client, store interface with in-memory and Supabase implementations and the
  SQL schema, pipelines (backfill, sync, details, reclean), command line
  interface and nightly GitHub Actions workflow. Implemented and tested
  offline; not yet run against a live database.
- Weekly backfill schedule (Sundays) to pick up edits to known rounds, which
  the `/changes` endpoint does not report.

### Fixed

- The nightly sync no longer crashes on a round without a date; such rounds
  are skipped and counted in the run summary.

### Changed

- City aliases completed from the first load: spelling variants, one
  encoding glitch, and regions that Tech.eu stores in the city field.
- Size bounds for rounds without a known stage calibrated on real data:
  7 and 20 million euros (were 3 and 15).
- `report` now prints the share of companies with fetched details and with a
  website.
- Design spec and Phase 1 plan translated to English; the spec file is now
  `docs/superpowers/specs/2026-11-11-kaltstart-design.md`.

## Phase 0 - 2026-11-11

### Added

- Design specification, validated.
- Public documents: README, PRD, DECISIONS, CHANGELOG, CLAUDE.md.
- Implementation plan for Phase 1 (ingestion).
