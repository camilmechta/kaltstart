# Server and Web App (Phase 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI app that renders the Kaltstart pages (sign-up, profile, company list, company page with free preview and "Keep this mail", My mails) on top of Supabase, enforcing the reservation rules on the server.

**Architecture:** Server-rendered HTML (FastAPI + Jinja2) styled by the `DESIGN.md` tokens, a tiny vanilla JavaScript file, a `Store` protocol with in-memory and Supabase versions, an `Auth` protocol with fake and Supabase versions, and pure functions for every rule. The browser only talks to the app; the app uses the service key.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, Jinja2, python-multipart, itsdangerous, supabase-py, pytest with FastAPI's `TestClient`.

**Spec:** `docs/superpowers/specs/2026-11-16-phase-4-web-app-design.md` · Design: `DESIGN.md` · Parent: `docs/superpowers/specs/2026-11-11-kaltstart-design.md`

## Global Constraints

- The app never sends mail, never calls an AI, and the browser never calls Supabase.
- Every rule is checked on the server: reservation (spec 7.1), ownership of profiles, showcases and mails, the choice of person and address (re-derived on the server, spec 9b point 4).
- A suggested person is used only after an explicit "Yes" (D60); a preview stores nothing; only "Keep this mail" takes a slot.
- No name, address, mail body or showcase text in any log line; errors log the route and the exception class only.
- Interface in English; pages follow `DESIGN.md`: CSS variables only, dark by default with a light theme, usable at 360px wide, one primary button per screen.
- Tests never reach the network: in-memory store and fake auth. Invented people and companies on `example.ch`, `example.de`, `example.com`.
- No secret in the repository: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `SESSION_SECRET`, `REMOVAL_CONTACT` come from the environment; the invitation code lives in the `app_settings` table.
- Downloading the Geist font files needs the owner's approval first (state file names, source and size).
- Test first. Commits `type: description`, author Camil Mechta, no co-author line. `DECISIONS.md` and `CHANGELOG.md` updated at the end.

## Review Focus

1. A student opens `/mails/<id>` of another student, or posts "Keep" for another student's company choice: 404 / refusal. Test in Task 6 and Task 8.
2. Two "Keep this mail" requests for the last slot of a company: only one succeeds in the in-memory store (a lock per company). Test in Task 2.
3. A form posted without or with a wrong CSRF token: 403, nothing changes. Test in Task 4.
4. A student whose profile is incomplete clicks "Generate": a clear message naming the missing fields with a link to the profile, not an error page. Test in Task 8.
5. A company excluded as a whole after the list was rendered: its page answers 404. Test in Task 7.

---

### Task 1: Migration `0004_students.sql`

**Files:**
- Create: `supabase/migrations/0004_students.sql`
- Test: `tests/api/__init__.py`, `tests/api/test_migration_0004.py`

**Interfaces:**
- Produces tables `app_settings(key text primary key, value text not null)`, `profiles`, `showcases`, `mails` with the columns of spec section 6 plus `mails.person_key text`, `mails.person_choice text check in ('suggested','other_on_list','typed','team')`, `mails.status text check in ('generated','copied','sent','human_reply','positive_reply','abandoned')`, timestamps `created_at`, `copied_at`, `sent_at`, `human_reply_at`, `positive_reply_at`, `abandoned_at`; `mails.student_id` nullable (anonymised mails).
- Produces SQL function `reserve_mail(p_student_id uuid, p_company_id text, p_person_key text, p_row jsonb) returns jsonb` → `{"ok": true, "id": ...}` or `{"ok": false, "reason": "company_full"|"student_pending"|"company_done"|"person_done", "frees_on": date|null}`, taking `pg_advisory_xact_lock(hashtext(p_company_id))`.
- Produces trigger `check_invitation_code` before insert on `auth.users`, comparing `new.raw_user_meta_data->>'invitation_code'` with `app_settings.value where key = 'invitation_code'`.
- Replaces `exclude_person` and `exclude_company` (same signatures and return types as 0003) so that they also set `person_name` and `person_source_url` to null in that company's `mails`.

- [ ] **Step 1: Write the failing test**: reads the file as text; asserts the four tables are created with row level security enabled and no policy; `reserve_mail` exists, takes the advisory lock and names the four reasons; the trigger function compares with `app_settings`; `exclude_person` and `exclude_company` are recreated and update `mails`; every new function is revoked from `public, anon, authenticated`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/api -q`. Expected: FAIL, file not found.
- [ ] **Step 3: Write the migration.** Counting rules exactly as spec 7.1: company cap counts mails of the company with `status <> 'abandoned'` and `created_at > now() - interval '30 days'`; pending counts the student's mails in `generated`/`copied` with `created_at > now() - interval '7 days'`; `frees_on` = oldest counting `created_at` + 30 days.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: students, mails and reservation in the database`.

### Task 2: Rules as pure functions

**Files:**
- Create: `src/kaltstart/api/__init__.py`, `src/kaltstart/api/rules.py`
- Test: `tests/api/test_rules.py`

**Interfaces:**
- Produces in `rules.py`:
  - Constants `COMPANY_CAP = 3`, `CAP_DAYS = 30`, `PENDING_LIMIT = 5`, `PRESUMED_SENT_DAYS = 7`, `REMINDER_HOURS = 72`.
  - `@dataclass(frozen=True) class MailRecord(id: str, student_id: str | None, company_id: str, person_key: str | None, status: str, created_at: datetime)`
  - `shown_status(mail: MailRecord, now: datetime) -> str`: `"presumed_sent"` for `generated`/`copied` older than 7 days, else the status.
  - `refusal(student_id: str, company_id: str, person_key: str | None, mails: Sequence[MailRecord], now: datetime) -> Refusal | None` with `Refusal(reason: str, frees_on: date | None)`; reasons `"company_full"`, `"student_pending"`, `"company_done"`, `"person_done"`, checked in that order.
  - `pending_count(student_id, mails, now) -> int`, `needs_reminder(mail, now) -> bool` (72 h ≤ age < 7 days and status `generated`/`copied`), `last_slot(company_id, mails, now) -> bool`.

- [ ] **Step 1: Write the failing tests**: each reason with the smallest set of mails that triggers it; the 30-day boundary (a mail 30 days old exactly no longer counts; 29 days 23 hours counts); abandoned mails count for nothing; a presumed-sent mail counts for the company cap and not for pending; `frees_on` is the oldest counting mail + 30 days; a person already written to at another company triggers `person_done`; anonymised mails (`student_id=None`) still count for the company cap.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/api/test_rules.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: reservation and tracking rules`.

### Task 3: The app's store

**Files:**
- Create: `src/kaltstart/api/store.py`, `src/kaltstart/api/supabase_store.py`, `src/kaltstart/api/seed.py`
- Test: `tests/api/test_store.py`, `tests/api/test_supabase_store.py`

**Interfaces:**
- Produces frozen dataclasses in `store.py`: `Profile` (fields of spec 6 for `profiles`), `Showcase(position: int, text_en: str | None, text_de: str | None)`, `CompanyRow` (id, name, country, city, sector, size_category, round fields for `mailgen.Round`, round date, description, website, source_url), `PersonRow` (name, title, categories, level, source_url, read_at), `EmailRow` (address, type, source_url), `Mail` (stored mail, all spec 6 columns).
- Produces `AppStore` protocol and `InMemoryAppStore` with: `invitation_code() -> str`; `profile(student_id) -> Profile | None`; `save_profile(Profile)`; `showcases(student_id) -> list[Showcase]`; `save_showcases(student_id, list[Showcase])`; `companies(filters: ListFilters, student_id: str, now: datetime) -> tuple[list[CompanyRow], int]` (eligible per spec 7.2, sorted by round date, 50 per page, total count); `company(company_id) -> CompanyRow | None` (None when excluded or not eligible); `people(company_id) -> list[PersonRow]`; `emails(company_id) -> list[EmailRow]`; `mail_records(company_id=None, student_id=None) -> list[rules.MailRecord]`; `reserve(student_id, company_id, person_key, mail: Mail, now) -> rules.Refusal | str` (the new id; the in-memory version holds a per-company `threading.Lock`); `mails(student_id) -> list[Mail]`; `mail(student_id, mail_id) -> Mail | None`; `set_status(student_id, mail_id, status, now) -> bool`; `delete_student(student_id)` (anonymises mails per spec 9b point 7).
- `ListFilters(query: str = "", countries: tuple[str, ...] = (), sectors: tuple[str, ...] = (), sizes: tuple[str, ...] = (), months: int = 12, page: int = 1)`.
- `SupabaseAppStore.from_env()` implements the same protocol; `reserve` calls the `reserve_mail` RPC.
- `seed.py`: `seeded_store(now: datetime) -> InMemoryAppStore` with about 30 invented companies in the three countries, people and addresses on example domains, rounds over the last 12 months, and one full company.

- [ ] **Step 1: Write the failing tests** for the in-memory store: eligibility (no address → absent, no recent round → absent, excluded → absent, full → absent unless the student wrote to it), each filter, paging (51 companies → 2 pages), status changes only on the student's own mail, deletion anonymises; concurrency: 10 threads keep a mail for the last slot of the same company → exactly one id returned. For `SupabaseAppStore`, with the recording fake client of Phase 2: the select columns and filters of `companies`, the RPC call of `reserve`, the anonymising update of `delete_student`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/api -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the three files.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: app store, in memory and on Supabase, with invented seed data`.

### Task 4: App skeleton, auth, session, CSRF, layout

**Files:**
- Modify: `pyproject.toml` (add `fastapi`, `uvicorn[standard]`, `python-multipart`, `itsdangerous`; package data for `api/templates/**` and `api/static/**`)
- Create: `src/kaltstart/api/app.py`, `auth.py`, `session.py`, `__main__.py`, `templates/base.html`, `templates/signin.html`, `templates/signup.html`, `static/app.css`, `static/app.js`, `static/icons.html` (Lucide SVG macros)
- Test: `tests/api/test_auth.py`, `tests/api/test_layout.py`

**Interfaces:**
- `auth.py`: `Auth` protocol with `sign_up(email, password, invitation_code) -> SignUpResult`, `sign_in(email, password) -> Tokens | None`, `refresh(refresh_token) -> Tokens | None`, `user_id(access_token) -> str | None`, `delete_user(user_id)`; `FakeAuth` (in memory, confirms at once) and `SupabaseAuth.from_env()`.
- `app.py`: `create_app(store: AppStore, auth: Auth, *, session_secret: str, removal_contact: str, now: Callable[[], datetime]) -> FastAPI`.
- `session.py`: signed HttpOnly, Secure, SameSite=Lax cookie holding the tokens; `csrf_token(request) -> str` and a dependency that rejects a POST without the right token (403); sign-up limited to 10 attempts per IP per hour (in memory).
- `__main__.py`: `python -m kaltstart.api` (real, from the environment) and `python -m kaltstart.api --dev` (FakeAuth, `seed.seeded_store`, a random session secret, `http://127.0.0.1:8000`).
- `static/app.css`: every token of `DESIGN.md` as CSS variables for dark (default) and light (`[data-theme=light]` and `prefers-color-scheme`), base styles, buttons, inputs, rows, tags, notices; `static/app.js`: copy buttons, theme toggle in `localStorage`, live word counters on `[data-max-words]`.

- [ ] **Step 0: Ask the owner** before downloading the Geist and Geist Mono woff2 files (OFL) from the official repository; if refused, fall back to the system font stack in `app.css`.
- [ ] **Step 1: Write the failing tests**: sign-up with a wrong code shows the generic error and creates nobody; with the right code creates the user and asks to confirm the e-mail; the 11th attempt in an hour from one IP is refused; sign-in sets the cookie and redirects to `/companies`; a protected page without a session redirects to `/signin?next=...`; a POST with a missing or wrong CSRF token answers 403; every page has the navigation, the footer with the removal contact, the theme toggle, `<meta name="viewport">`, and links `app.css`; `app.css` defines every token name of `DESIGN.md` in both themes.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/api -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: app skeleton with sign-up, sign-in, session and the design tokens`.

### Task 5: Profile and account deletion

**Files:**
- Create: `templates/profile.html`; Modify: `app.py`
- Test: `tests/api/test_profile.py`

- [ ] **Step 1: Write the failing tests**: GET `/profile` shows the fields of the wireframe; POST saves them; showcase 1 required, German version required only when German is ticked; a showcase over 60 words or 400 characters is refused with the field named; programme over 70 characters refused; the role options are the five `mailgen.ROLES`; "Delete my account" asks for confirmation, then removes profile, showcases and auth user and anonymises mails; another student's profile is never shown.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: profile page and account deletion`.

### Task 6: My mails

**Files:**
- Create: `templates/mails.html`, `templates/mail.html`; Modify: `app.py`
- Test: `tests/api/test_mails.py`

- [ ] **Step 1: Write the failing tests**: the list shows the student's mails newest first with `rules.shown_status`; the reminder appears for a mail between 72 h and 7 days old in `generated`/`copied`; "I sent it", "Got a reply", "Positive reply", "Abandon" move the status (only forward, abandon from `generated`/`copied` only); copying the body (POST `/mails/{id}/copied`) moves `generated` to `copied`; `/mails/{id}` of another student is 404 (Review Focus 1); the navigation pill shows "N / 5 pending".
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: my mails with statuses and the 72-hour reminder`.

### Task 7: Company list

**Files:**
- Create: `templates/companies.html`; Modify: `app.py`
- Test: `tests/api/test_companies.py`

- [ ] **Step 1: Write the failing tests**: filters in the query string (`q`, `country`, `sector`, `size`, `months`, `page`) reach `store.companies`; defaults come from the profile's preferences; each row shows name, sector, amount and stage (via `mailgen.phrases.amount` and `round_name`), month, city and country, contact kind ("Person suggested", "Careers address", "General address"); "Last slot" when `rules.last_slot`; no slot counter anywhere; the page is usable without a complete profile; an excluded company's page `/companies/{id}` answers 404 (Review Focus 5).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: company list with filters`.

### Task 8: Company page: who, preview, keep, copy

**Files:**
- Create: `templates/company.html`, `src/kaltstart/api/compose.py`; Modify: `app.py`
- Test: `tests/api/test_compose.py`, `tests/api/test_company_page.py`

**Interfaces:**
- `compose.py`: `ROLE_TO_SELECTION = {"product": "product", "growth": "growth", "data": "data", "operations": "ops", "business_development": "bd"}`; `choose(company, people, emails, profile, choice: str, person_index: int | None, typed_name: str | None, typed_title: str | None) -> Recipient` (re-derives person and address on the server; `Recipient(person_name, person_source_url, address, address_type, person_choice, person_key)`); `to_mailgen(profile, showcases, company, recipient, chosen_showcase) -> (mailgen.Student, mailgen.Company, mailgen.Round, mailgen.Contact)`.

- [ ] **Step 1: Write the failing tests**: the suggested person is `selection.choose_person` with the mapped role; "Someone else" lists the other people; a posted `person_index` outside the list is refused; typed name and title are used for this mail only; "team" gives no person and the careers then generic address; POST `/companies/{id}/preview` renders the mail without storing anything and shows refusals 7.1 early; an incomplete profile gives a message naming the fields with a link to the profile (Review Focus 4); `MissingData` and `TooLong` become one sentence; POST `/companies/{id}/keep` re-derives the recipient, regenerates the same mail from the same choices, calls `store.reserve`, and on success redirects to `/mails/{id}` with the Copy buttons; on refusal shows the reason and, for `company_full`, the date; keeping twice for the same company is refused (`company_done`); no form field can set the address or the suggested person's name directly (Review Focus 1).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: company page with free preview and keep`.

### Task 9: Logs, Dockerfile and documents

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `src/kaltstart/api/logging.py`; Modify: `app.py`, `README.md`, `CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`
- Test: `tests/api/test_logs.py`

- [ ] **Step 1: Write the failing test**: a full journey with the test client (sign-up, profile with a known showcase, preview, keep, copy, status) while capturing all logs; no log record contains the invented names, addresses, the showcase or the mail body; an exception in a route logs the route and the class name only.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the logging setup (uvicorn access log without query strings) and the `Dockerfile` (python:3.12-slim, `pip install .`, `uvicorn kaltstart.api.app:app_from_env --host 0.0.0.0 --port $PORT`).
- [ ] **Step 4:** README: how to try the app with `python -m kaltstart.api --dev`, how to deploy (environment variables, the SQL step for the invitation code), the removal contact. CLAUDE.md: the new commands and `api/`. DECISIONS: one row for Phase 4 (all in Python, Supabase Auth through the server, free preview, anonymised deletion, trigger for the invitation code). CHANGELOG.
- [ ] **Step 5: Run** `.venv/bin/pytest -q`. Expected: all pass. **Commit** `feat: logs without personal data, Dockerfile and documents`.

### Task 10: The owner's journey, then deployment

No new code unless the journey shows a fault (each fault: a failing test first).

- [ ] **Step 1:** Start `python -m kaltstart.api --dev` and walk the journey in the built-in browser at phone and desktop widths; fix what the owner or the walk finds.
- [ ] **Step 2:** The owner tries the journey himself in the `--dev` app.
- [ ] **Step 3:** With the owner: choose the host after checking current free offers on their own sites, apply `0004` in the SQL editor, set the invitation code there, give `REMOVAL_CONTACT`, deploy, try sign-up with a test account on the deployed app. Each outward step needs his approval.
