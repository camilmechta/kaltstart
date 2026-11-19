# Privacy Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public `/privacy` page, linked from every footer and from sign-up.

**Architecture:** One more public route in `api/app.py` rendering `privacy.html`, built like `about.html`; the contact is the `removal_contact` the page context already carries.

**Tech Stack:** FastAPI, Jinja2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-19-privacy-page-design.md`

## Global Constraints

- English only; short sentences; the seven sections of the spec, in its order, plus "Last updated: 19 November 2026".
- The contact is always `{{ removal_contact }}`, never written out.
- No personal name of the owner anywhere on the page.
- Facts must match the code: session cookie `COOKIE_DAYS = 14` (`api/session.py`); companies kept 365 days after their last round (`RECENT_ROUND_DAYS`, contacts); Render Frankfurt; Supabase Paris.
- Test first, seen failing; full suite before each commit; commits `type: description`, owner as author, no attribution line.

## Review Focus

1. A signed-in student opening `/privacy`: the page shows, with the signed-in header (test).
2. The page's 14 days and 12 months drift from the code: tests tie them to `COOKIE_DAYS` and `RECENT_ROUND_DAYS`.
3. Phone width: no horizontal scroll (checked in the local app).

---

### Task 1: The page and its links

**Files:**
- Create: `src/kaltstart/api/templates/privacy.html`
- Modify: `src/kaltstart/api/app.py` (route `GET /privacy` next to `/about`)
- Modify: `src/kaltstart/api/templates/base.html` (footer link), `src/kaltstart/api/templates/signup.html` (line under the button)
- Test: `tests/api/test_privacy.py`

- [ ] **Step 1: Write the failing tests** in `tests/api/test_privacy.py`, using the fixtures of `tests/api/test_about.py`:
  - `test_the_privacy_page_is_public`: `GET /privacy` is 200 without signing in; contains "r@example.com" (the test removal contact), "Render", "Frankfurt", "Supabase", "Paris", "never sends", "When the project ends".
  - `test_the_page_matches_the_code`: `COOKIE_DAYS == 14` and "14 days" in the page; `RECENT_ROUND_DAYS == 365` and "12 months" in the page.
  - `test_every_page_links_to_privacy`: for `/`, `/about`, `/signin`, `/signup` and, signed in (`ready(client)`), `/companies`, `/profile`, `/mails`: `'href="/privacy"'` in the page.
  - `test_the_signup_page_explains_the_data_use`: "How Kaltstart uses your data" in `/signup`.
  - `test_a_signed_in_student_can_read_it`: after `ready(client)`, `/privacy` is 200.
- [ ] **Step 2: Run** `.venv/bin/pytest -q tests/api/test_privacy.py`. Expected: FAIL (404, missing links).
- [ ] **Step 3: Implement** the route, the template (seven `card` sections like `about.html`, kicker "Privacy", title "Your data on Kaltstart"), the footer link "Privacy" after "About Kaltstart", and under the sign-up button `<p class="muted">How Kaltstart uses your data: <a href="/privacy">Privacy</a>.</p>` (reuse an existing small-text class from `app.css`).
- [ ] **Step 4: Run** the full suite: no `failed`.
- [ ] **Step 5: Commit** `feat: a privacy page, linked from every page and from sign-up`.

### Task 2: Check and document

- [ ] **Step 1:** Restart the local dev app, open `/privacy` at desktop width and at 375 px: no horizontal scroll; screenshot.
- [ ] **Step 2:** `DECISIONS.md` (D94: a privacy page, why, rejected: in `/about`, external document) and `CHANGELOG.md` (Added). Full suite, commit `docs: privacy page in D94 and the changelog`.
