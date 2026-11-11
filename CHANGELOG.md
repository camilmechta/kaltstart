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

## Phase 0 - 2026-11-11

### Added

- Design specification, validated.
- Public documents: README, PRD, DECISIONS, CHANGELOG, CLAUDE.md.
- Implementation plan for Phase 1 (ingestion).
