# Did they reply? Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 14 days after a mail is marked sent, ask the student whether they got a reply, with a stored "No reply yet" answer.

**Architecture:** A new mail status `no_reply` (migration `0012`), a pure rule `rules.needs_reply_reminder`, notices on My mails and one line on the company list. Executed in this session (native), Opus review at the end.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, Supabase (PostgreSQL), pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-reply-reminder-design.md`

## Global Constraints

- The app sends nothing. No AI call. Everything in English.
- Status name `no_reply`, label "No reply", button "No reply yet"; reminder after `REPLY_REMINDER_DAYS = 14` days counted from `sent_at`.
- Allowed moves: `sent` to `no_reply`, `human_reply`, `positive_reply`; `no_reply` to `human_reply`, `positive_reply`; never back to `no_reply`.
- Migration pasted by the owner before the push; `check_migrations.sql` gains `m0012_no_reply`.
- Test written and seen failing before the code.

## Review Focus

1. A `sent` mail with no `sent` date (old rows): no reminder, no crash.
2. A mail marked `no_reply`, then `human_reply`: reminder gone, counted as a reply in the strip.
3. A mail of another student never shows in the reminders or the count.
4. A reminder at exactly 14 days shows; at 13 days and 23 hours it does not.
5. A redacted mail (removed on request) still gets the reminder buttons without showing removed text.

---

### Task 1: Migration 0012

**Files:** Create `supabase/migrations/0012_no_reply.sql`; Modify `supabase/check_migrations.sql`; Test `tests/sql/test_migration_check.py` (existing test covers it), `tests/sql/test_migrations_apply.py`.

- [ ] Add `m0012_no_reply` to `check_migrations.sql`: true when `mails_status_check` contains `no_reply` and column `mails.no_reply_at` exists. Run `.venv/bin/pytest -q tests/sql` and see the check test fail.
- [ ] Write the migration: drop and re-add `mails_status_check` with `no_reply`, `add column if not exists no_reply_at timestamptz`. Header comment as in `0011`.
- [ ] Add `test_a_mail_can_be_marked_no_reply` in `tests/sql/test_migrations_apply.py`: an update to `status = 'no_reply', no_reply_at = now()` succeeds. Run `tests/sql`: PASS.

### Task 2: The status and the rule

**Files:** Modify `src/kaltstart/api/store.py` (`STATUSES`, `Mail.record`), `supabase_store.py` (`_MAIL_COLUMNS`, `_COPIED`), `rules.py`, `pages.py` (`ORDER`, `LABELS`, progress), `templates/_status_actions.html`, `static/app.css`; Test `tests/api/test_rules.py` or `tests/api/test_mails.py`, `tests/api/test_supabase_store.py` if it lists columns.

**Produces:** `rules.REPLY_REMINDER_DAYS = 14`; `rules.needs_reply_reminder(status: str, sent_at: datetime | None, now: datetime) -> bool`; `Mail.sent_at` read from `status_dates.get("sent")`.

- [ ] Tests: `needs_reply_reminder("sent", now - 14 days, now)` is True; 13 days 23 hours False; `"no_reply"` False; `sent_at=None` False. Sent mail: posting `no_reply` sets the status and the label "No reply" shows; from `no_reply` posting `human_reply` works; from `human_reply` posting `no_reply` is refused (status unchanged); progress strip counts a `no_reply` mail as sent and not as a reply.
- [ ] Run, see them fail. Implement. ORDER becomes `sent 2, no_reply 3, human_reply 4, positive_reply 5`. Actions: `sent` offers Got a reply, Positive reply, No reply yet; `no_reply` offers Got a reply, Positive reply. CSS: `no_reply` pill uses the muted colour.
- [ ] Run the whole suite: PASS.

### Task 3: The reminders

**Files:** Modify `pages.py` (`my_mails`, company list), `templates/mails.html`, `templates/companies.html`; Test `tests/api/test_mails.py`, `tests/api/test_companies.py` (or where the progress strip is tested).

- [ ] Tests: a mail sent 15 days ago shows "was sent 15 days ago: did they reply?" with the three buttons on `/mails`; after "No reply yet" the notice is gone; the company list shows "1 mail sent 2 weeks ago or more: did they reply?" linking to `/mails`, "2 mails" for two; nothing for a mail sent 3 days ago; another student's old sent mail adds nothing.
- [ ] Run, see them fail. Implement: reminders oldest sent first; the line under the progress strip.
- [ ] Run the whole suite: PASS.

### Task 4: Documents and review

- [ ] D104 in `DECISIONS.md`, a CHANGELOG line, migration range `0012` in `docs/operations.md`.
- [ ] Opus review of the diff; fix what it finds with tests first; full suite; commit locally.
