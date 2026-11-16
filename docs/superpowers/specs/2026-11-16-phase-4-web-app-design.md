# Phase 4: the server and the web app

Date: 2026-11-16. Status: written after a conversation with the project
owner, who approved the screens as grey wireframes and chose the visual
direction (`DESIGN.md`). Points marked "builder's call" were decided by the
author of this document.

Parent: `2026-11-11-kaltstart-design.md` (sections 5, 6.2, 6.4, 6.5, 7.2,
7.4, 8). Uses Phase 2 (`kaltstart.contacts.selection`) and Phase 3
(`kaltstart.mailgen`). This document replaces the parent's open choice of a
front tool.

## 1. Intent

The app HSG students use, from sign-up to a mail copied into their own
mailbox. Phases 1 to 3 already fill the database every night and can write
a mail; this phase puts them in front of students, with the rules that
protect founders (3 mails per company per 30 days) and the tracking that
Phase 5 measures (reply rates).

Done when, as the parent says, a student goes from sign-up to a copied mail
without help.

## 2. Goals, non-goals, anti-goals

Goals: sign-up with the invitation code; a profile; the company list with
filters; the company page in three steps (who, generate, copy); "My mails"
with statuses and the 72-hour reminder; account deletion; the reservation
rules enforced by the server; the visual design of `DESIGN.md`, light and
dark, usable on a phone.

Non-goals: sending mail (never: a hard rule); a page for the owner (Phase 5
figures come from a database query); a public removal-request form (removal
stays in the SQL editor, D61, with an address shown in the footer); any
language but English in the interface; payments.

Anti-goals, failures even if every test passes:

- A student sees another student's profile or mails, or who wrote to a
  company.
- A company gets a fourth mail in 30 days, or a student a sixth pending
  mail, because two clicks raced.
- A suggested person is used in a mail without the student's click on
  "Yes" (D60).
- A name, an address or a mail body in a log.
- A dependency on a paid service to keep the app alive, or on a tool only
  its vendor can edit (the owner's reason for leaving Lovable aside).

## 3. Constraints

From the parent and `CLAUDE.md`: no AI at runtime; business rules checked
by the server, never by the browser alone; Supabase as the database; no
secret in the repository; everything in English; test first; tests never
reach the network. Hosting free while building, paid only if the 20-student
test starts (the owner's condition), so the app must move host without code
changes.

## 4. Approaches

Front tool, decided with the owner:

1. **Lovable** with a Python server for generation. Rejected by the owner:
   its code is only comfortably editable inside a paid tool.
2. **A React app** with the Python server. Rejected: two languages, two
   toolchains and two deployments to keep alive, dependencies that age fast.
3. **All in Python** (chosen): FastAPI renders HTML pages with Jinja2, as
   the mail generator already does; a little plain JavaScript for copying,
   the theme toggle and live word counters. One repository, one language,
   one deployment, every rule tested with pytest. Each click loads a page,
   which is fast enough for this app.

Authentication (builder's call): **Supabase Auth** (email and password,
confirmation e-mail, password reset), called by the server. The browser
never talks to Supabase: it only talks to the app. Writing our own
authentication was rejected (passwords are not ours to store).

## 5. Architecture

```
browser ──HTML forms──> FastAPI app (src/kaltstart/api/) ──> Supabase (Postgres + Auth)
                              │
                              ├── kaltstart.contacts.selection (who to propose)
                              └── kaltstart.mailgen (the mail)
```

- `src/kaltstart/api/`: the FastAPI application, its routes, the session,
  and a `Store` with an in-memory version for tests and a Supabase version,
  as in Phases 1 and 2.
- `src/kaltstart/api/templates/`: Jinja2 pages; `static/`: one CSS file
  holding the `DESIGN.md` tokens, the Geist woff2 files, Lucide icons as
  inline SVG, one small JavaScript file.
- The server uses the service key for database access and checks every
  ownership rule in code. The four student tables keep row level security
  on with no policy, like every other table: only the server reads them
  (builder's call: with no browser access to Supabase, per-user policies
  would add nothing but a second place to get wrong).
- Session: the Supabase access and refresh tokens in an HttpOnly, Secure,
  SameSite=Lax cookie; every form carries a CSRF token.
- Configuration from environment variables: `SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY` (for Supabase Auth calls),
  `INVITATION_CODE`, `SESSION_SECRET`, `REMOVAL_CONTACT` (the address shown
  in the footer for removal requests).
- Deployment: a `Dockerfile` running uvicorn, so any host that runs a
  container works. The host is chosen in the plan, after checking current
  offers: a free plan now, a paid always-on plan if the test starts.

## 6. Data

Migration `0004_students.sql`.

| Table | One row | Columns |
|---|---|---|
| `profiles` | A student (id = Supabase Auth user id) | first name, last name, programme, languages (`en`, `de`), target role, request type, start date, duration in months or workload in per cent, link, preferred countries, preferred sectors, created and updated dates |
| `showcases` | A showcase sentence (two at most, D71) | student, position (1 or 2), text in English, text in German |
| `mails` | A generated mail | student, company, round, contact address and its type, person name (as used) and how it was chosen (`suggested`, `other_on_list`, `typed`, `team`), person source page when suggested, style, language, company line (or null), subject, body, status, created date and one date per status change |

The parent called them `experiences` and `emails`; `showcases` and `mails`
avoid confusion with `contact_emails` (builder's call).

Statuses (parent 6.4): `generated`, `copied`, `sent`, `human_reply`,
`positive_reply`, `abandoned`. "Presumed sent" is not stored: a mail still
`generated` or `copied` 7 days after creation reads as presumed sent
everywhere (builder's call: no nightly job to keep in step).

## 7. Rules

### 7.1 Reservation (parent 7.4)

Generating a mail is refused when:

1. the company has 3 non-abandoned mails created in the last 30 days, all
   students together (presumed-sent ones count);
2. the student has 5 mails `generated` or `copied` that are not presumed
   sent;
3. the student has a non-abandoned mail for this company;
4. the student has a non-abandoned mail for this person (same normalised
   name, `exclusions.normalise_name`, at the same company or another).

The refusal names the reason; for rule 1 it gives the date a slot frees.

The check and the insert happen in one transaction, in a SQL function
`reserve_mail(...)` that takes a per-company advisory lock, counts, and
inserts or returns the reason (builder's call: two students clicking
together on the last slot must not both get it). The same rules exist as a
pure Python function used by the in-memory store and tested on every case;
the SQL function mirrors it.

### 7.2 Company list

Eligible: a round in the last 365 days; at least one address in
`contact_emails`; not excluded; not full (rule 1). Companies the student
already wrote to stay visible to that student. Sorted by most recent round.
Filters: search on the name, country, sector, size category, round date
(last 3, 6 or 12 months); defaults from the profile's preferences. Fifty
per page. No slot counter; "Last slot" when one remains.

### 7.3 Company page

Top: name, sector, city and country, the round (amount, stage, month,
first investor), the Tech.eu description, links to the source and the
website.

Step 1, who: the person proposed by `selection.choose_person` for the
student's target role and the company's size, with the page it was read on
and its date. Buttons: "Yes, write to {first name}"; "Someone else on the
list" (the other people read for the company); "Enter a name myself" (name
and job title, used for this mail only and never stored elsewhere, parent
7.2); "No name, write to the team". The address comes from
`selection.choose_contact` for the chosen person, or the careers then
generic address for a typed name or the team; it is shown with a link to
the page it was read on. Nothing is generated before a choice.

Step 2, generate: style (default `mailgen.suggested_style`), language
(default `mailgen.choose_language`), showcase sentence (1 or 2), the
optional company sentence with a live word counter (35). A note says that
generating takes a slot. Refusals from rule 7.1 and from the generator
(`MissingData`, `TooLong`) appear as one sentence naming what to do.

Step 2 ends with a preview of the mail and the button "Keep this mail"
(section 9b, point 3); only keeping takes the slot.

Step 3, copy: three Copy buttons (address, subject, body); copying the
body moves the mail to `copied`. Buttons "I sent it" and "Abandon".

### 7.4 Profile and sign-up

Sign-up: e-mail, password, invitation code (compared on the server, in
constant time, with `INVITATION_CODE`); Supabase sends the confirmation
e-mail. The profile must be complete (the fields `mailgen` requires, and
showcase sentence 1 in English, plus German if the student ticks German)
before the first mail; the company list is open before. Live word counters
on showcase sentences (60). "Delete my account" removes the profile,
showcases, mails and the Supabase Auth user, after a confirmation.

### 7.5 My mails

All the student's mails, newest first, with status and next action; the
72-hour reminder above the list for mails `generated` or `copied` for more
than 72 hours and less than 7 days; the counter "N / 5 pending" also in the
navigation.

## 8. Errors

| Situation | Behaviour |
|---|---|
| Supabase unreachable | A plain error page, nothing half-written; the reservation is one transaction |
| Session expired | Back to sign-in, then to the page asked for |
| Wrong invitation code | Same message as any sign-up error, no hint |
| A page of another student's mail | 404 |
| Any exception | Logged with the route and the error class only, never the data |

## 9. Tests

- Every route with FastAPI's test client and the in-memory store: access
  without a session, another student's mail (404), each refusal of 7.1,
  each status change, account deletion.
- The reservation rules as a pure function: every rule, the 30-day and
  7-day boundaries, presumed sent, abandoned mails freeing a slot.
- The HTML of each page: the elements of section 7 present, no name of
  another student, the CSRF token in every form.
- The SQL migration as text (tables, functions, row level security), as in
  Phase 2; `reserve_mail` is checked once by the owner in the SQL editor
  with invented rows, since no test reaches the database.
- Logs never contain a name, address or body (a test on captured logs).

## 9b. Answers to the builder check (builder's calls unless marked)

1. **Invitation code.** Sign-up goes through the server, which calls
   Supabase Auth with the code in the user's metadata. A trigger on
   `auth.users` (migration `0004`) rejects any new user whose metadata does
   not carry the code stored in a private table `app_settings` (row level
   security on, no policy), so a direct call to Supabase with the public key
   cannot skip it. Supabase keeps sending the confirmation e-mail. The owner
   sets the code once in the SQL editor. Supabase's own sign-up rate limit
   applies; the server also allows at most 10 sign-up attempts per IP
   address per hour.
2. **Roles.** `profiles.target_role` stores the `mailgen.ROLES` spellings
   (`product`, `growth`, `data`, `operations`, `business_development`); the
   app maps `operations` to `ops` and `business_development` to `bd` before
   calling `selection.choose_person`. The role is required before the first
   mail.
3. **Preview before a slot is taken** (the owner's decision): "Generate"
   shows the mail without reserving anything; the student may change the
   style, language, showcase sentence or company sentence and generate again
   as often as they like. The slot is taken only by "Keep this mail", which
   runs `reserve_mail` and stores the mail as `generated`; the Copy buttons
   appear after it. Rules 7.1 are checked at "Generate" too, so a student
   does not polish a mail they cannot keep, and again at "Keep". Abandoned
   then means a kept mail the student will not send. Previews are not
   stored.
4. **Who and which address** are re-derived on the server from
   `contact_people` and `contact_emails` for `suggested` and `other_on_list`;
   the form only sends which choice and, for `other_on_list`, which person.
   Only a typed name and title are free text.
5. **Removal and stored mails.** `mails` keeps the person name for the
   student's own record (a typed name included) and a `person_key`
   (`exclusions.person_key`) for rule 4. Migration `0004` extends
   `exclude_person` and `exclude_company` to blank the person name and
   source page of that company's mails, keeping the key.
6. **Running without credentials.** `python -m kaltstart.api --dev` starts
   the app with a fake authentication and an in-memory store seeded with
   invented companies, people and rounds, so the owner can try the whole
   journey on the Mac before anything is deployed. The authentication
   client is behind an interface with a real (Supabase) and a fake version.
7. **Account deletion** removes the profile, showcases and Supabase Auth
   user, and anonymises the student's mails (student id null; subject,
   body, person name, company line and address removed; company, round,
   style, language, statuses and dates kept), so the 30-day cap and the
   Phase 5 rates stay right. "The date a slot frees" is the oldest of the 3
   counting mails plus 30 days. Rule 3 has no time limit, as the parent
   says.
8. **Exclusions.** Contact rows are already filtered when the scraper
   writes them (D61, D63); the app only checks whole-company exclusions when
   listing.

## 10. Open points for the owner

- The address shown in the footer for removal requests (`REMOVAL_CONTACT`):
  given by the owner before deployment; it lives only in the server's
  configuration, never in the repository.
- The host, chosen in the plan after checking current free offers.

## 11. Left to the builder

Route names, the exact copy of every label and message (English, short,
in the spirit of the wireframes), pagination details, the small
JavaScript, and how the CSS is organised, as long as it follows
`DESIGN.md`.
