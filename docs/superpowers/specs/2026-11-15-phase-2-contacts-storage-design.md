# Phase 2, second plan: storing contacts and reading sites every night

Date: 2026-11-15. Status: approved by the project owner in conversation,
except the points marked "builder's call" and the open point of section 12.

Parent documents: `2026-11-11-kaltstart-design.md` (sections 6.1, 6.3, 7.2
and 9), `2026-11-12-phase-2-contact-measurement-design.md` (the scraper) and
`2026-11-13-phase-2-people-design.md` (people, section 6 on personal data).

## 1. Intent

The contact scraper has only run on samples so far, and its results live in
files on the owner's machine. This plan connects it for real: every night it
reads the sites of the companies in the database and stores what it finds in
Supabase, so that the application (Phases 3 to 5) can propose an address and
suggest a person for a company.

Why now: nine measurements on 180 Swiss companies have settled what the
scraper can be trusted for. No reported address was ever wrong. People are
right for about nine lists in ten and are therefore a suggestion the student
confirms on the source page (decision D60).

## 2. Goals, non-goals, anti-goals

Goals:

- After one manual run, every eligible company has been visited once and its
  addresses and people are in the database.
- Every night, new companies are read, failed ones are tried again, and
  companies read more than 30 days ago are read again.
- A person who left a company's site disappears from the database at the
  next reading.
- The owner can remove a company or a person on request, and the scraper
  never adds them again.

Non-goals (other phases or later):

- Choosing the contact shown to a student: `selection.py` already does it,
  and the server calls it at request time (Phase 4), because the choice
  depends on the student's target role.
- The screen where the student confirms the person (Phase 4).
- A public form to ask for removal, and the address people write to
  (Phase 4, when the app exists).
- Germany and Austria: the code takes the country as a setting, but the
  nightly run reads Switzerland only until the scraper has been measured on
  20 companies of each country.

Anti-goals, which would make this a failure even if it works:

- A name or an address in a public place. The repository is public, so its
  GitHub Actions logs are public too: no log line, workflow input or summary
  may ever contain a person's name or an email address.
- A stale contact kept for months, or a removed person coming back.
- A run that hammers company sites: the politeness rules of the scraper stay
  as they are, and a site is read once a month at most in normal operation.

## 3. Constraints

From `CLAUDE.md` and the parent specs, unchanged: no AI API at runtime; only
the company's own site, `robots.txt` obeyed, at least 2 seconds between
requests to a site, at most 8 pages per company, no project name in the
`User-Agent` and no browser imitation; no real page, name or address in the
repository; no test makes a network call; test first; no credentials on the
owner's machine, so every database command runs in GitHub Actions or in the
Supabase SQL editor.

Sizes, read from the database on 2026-11-15: 789 companies, 786 with a
website; 261 rounds in Switzerland (about 245 companies), 515 in Germany, 64
in Austria. One company takes 20 to 30 seconds. A GitHub job is limited here
to 180 minutes.

## 4. Approaches

Where the nightly work runs:

1. **A separate workflow `contacts`** (chosen by the owner). Its own
   schedule one hour after the ingestion, its own time limit, concurrency
   group and log. A failure of the ingestion does not stop the contacts and
   the other way round.
2. One more step in the `nightly` workflow. One file, but both jobs share
   the 180 minutes, an ingestion failure blocks the contacts and the logs
   mix. Rejected.
3. A server that works through a queue. Rejected by decision D9: the nightly
   work needs no server.

How a reading is stored (builder's call, accepted by the owner):

- **Replace everything for the company at each successful reading**
  (chosen). The freshness rule holds without any comparison logic.
- Compare the new reading with the stored rows and update, insert or delete
  one by one. Keeps a "first seen" date nobody has asked for, at the price
  of more code and more ways to keep a stale row. Rejected.

## 5. Data

One migration, `supabase/migrations/0002_contacts.sql`.

### 5.1 Reading state, on `companies`

| Column | Type | Meaning |
|---|---|---|
| `contacts_checked_at` | timestamptz, null | Last attempt. Null: never visited |
| `contacts_outcome` | text, null | `ok` when an address was found, otherwise one of the scraper's failure causes (`scrape.FAILURES`) |
| `contacts_attempts` | int, default 0 | Consecutive `unreachable` outcomes |
| `contacts_next_at` | timestamptz, null | When the company is due again. Null: due now |

### 5.2 `contact_emails`

One row per address found on a company's site.

| Column | Type |
|---|---|
| `company_id` | text, references `companies(id)` on delete cascade |
| `address` | text, lower case |
| `type` | text, one of `personal`, `careers`, `generic` |
| `source_url` | text |
| `read_at` | timestamptz |

Primary key: `(company_id, address)`.

### 5.3 `contact_people`

One row per person suggested for a company.

| Column | Type |
|---|---|
| `company_id` | text, references `companies(id)` on delete cascade |
| `name` | text |
| `title` | text, as the site writes it |
| `categories` | text[] |
| `level` | text, `head` or `manager` |
| `source_url` | text |
| `read_at` | timestamptz |

Primary key: `(company_id, name)`.

The parent spec planned a single `contacts` table with a `confidence`
column. Two tables replace it because an address and a person share almost
no column, and confidence is not stored: it is computed with the proposed
contact, which depends on the student (builder's call).

### 5.4 `contact_exclusions`

| Column | Type | Meaning |
|---|---|---|
| `id` | bigint identity, primary key | |
| `company_id` | text, references `companies(id)` | |
| `person_key` | text, null | Null: the whole company is excluded. Otherwise the key of one person |
| `created_at` | timestamptz, default now() | |

Unique on `(company_id, coalesce(person_key, ''))`.

`person_key` is the SHA-256, in hexadecimal, of the company id, a line
break, and the normalised name (trimmed, inner whitespace collapsed to one
space, lower case). The list of people who asked to disappear is therefore
not itself a list of names. This protects against casual reading, not
against somebody who already has a name and tests it; the design says so
rather than claim more.

### 5.5 `contact_runs`

One row per run: `id`, `started_at`, `finished_at`, `status` (`success` or
`failed`), `country`, `companies_visited`, `with_address`, `with_people`,
`outcomes` (jsonb: count per outcome), `error`. Numbers only.

A table of its own rather than more columns on `sync_runs`, whose columns
are about Tech.eu (builder's call).

### 5.6 Access

Row level security is enabled on the four new tables, without any policy,
as on the existing tables: only the service key reads or writes them. The
policies that let a signed-in student read one company's contacts belong to
Phase 4.

## 6. Which companies are read, and when

A company is eligible when its country is the run's country, it has a
website, it has a round dated within the last 365 days, and it is not
excluded as a whole.

A run takes the eligible companies that are due, in this order, up to
`--max` (default 300):

1. never visited (`contacts_checked_at` is null), oldest company first;
2. due again (`contacts_next_at` is in the past), the longest overdue first.

After each company, its state is written:

| Outcome | Next attempt | Stored rows |
|---|---|---|
| `ok`, or any cause where the site was read (`no_address`, `contact_form_only`, `other_domain_only`, `little_text`, `not_own_site`, `robots_forbidden`) | 30 days later; attempts back to 0 | Replaced by what was read (people may exist without an address) |
| `unreachable`, first and second time in a row | 7 days later | Kept as they are |
| `unreachable`, third time in a row | 30 days later; attempts back to 0 | Deleted |

`robots_forbidden` is a decision of the site: it is obeyed and checked again
a month later, not after a week.

The state is written after each company, not at the end of the run, so a
run that is stopped loses nothing and the next one continues.

At the start of each run, the rows of companies that have no round in the
last 365 days, or that are excluded, are deleted from `contact_emails` and
`contact_people`: data is not kept for companies the app no longer shows
(builder's call). The country setting is not a reason to delete: rows of
another country, once read, stay.

First run: launched by hand. About 245 Swiss companies fit in one run of 90
to 120 minutes. Thirty days later they all come due the same night; this is
accepted (one long run a month) rather than spreading the first pass.

## 7. Removal on request

The owner receives a request and acts by hand (chosen by the owner).

Two SQL functions created by the migration, run by the owner in the
Supabase SQL editor:

- `exclude_company(company_id text)`: adds the exclusion, deletes the
  company's rows in `contact_emails` and `contact_people`.
- `exclude_person(company_id text, person_name text)`: adds the exclusion
  with the person's key, deletes that person's row in `contact_people` and
  the `personal` addresses of that company whose local part carries the
  person's last name.

The functions run in the SQL editor and not through a GitHub workflow
input, as first discussed, because the repository is public: a name typed
into a workflow input would be printed in a public log. See section 12.

The scraper applies the exclusions before writing: an excluded company is
never visited; an excluded person is dropped from the people read, and so is
a personal address that `selection._owner` attributes to that person. The
Python key and the SQL key are the same function of the same inputs, and a
test pins a known value for both.

## 8. Code

New modules in `src/kaltstart/contacts/`, following the ingestion's pattern
(a `Store` protocol, an in-memory store for tests, a Supabase store):

| Module | Role |
|---|---|
| `store.py` | `ContactStore` protocol and `InMemoryContactStore` |
| `supabase_store.py` | The same on Supabase, service key from the environment |
| `exclusions.py` | Name normalisation, `person_key`, filtering a `CompanyResult` |
| `nightly.py` | One run: delete what is no longer eligible, pick the due companies, scrape each with the existing `scrape_company`, apply exclusions, write rows and state, record the run |

`__main__.py` gains two commands:

- `run [--country Switzerland] [--max 300]`
- `status [--country Switzerland]`: counts only (visited, with an address,
  with people, per outcome, due now).

Everything printed is a count or a company id. Never a name, an address or
a page.

## 9. Workflow

`.github/workflows/contacts.yml`:

- schedule: every night at 03:17 UTC, one hour after the ingestion's sync;
- manual run with a `command` choice (`run`, `status`) and free-text `args`;
- its own concurrency group, one run at a time, `timeout-minutes: 180`;
- the same two secrets as `nightly`.

GitHub notifies the owner by email when a run fails, as for the ingestion.

## 10. Errors

| Situation | Behaviour |
|---|---|
| One site fails in any way | `scrape_company` never raises; the outcome is recorded and the run goes on |
| The database refuses a write for one company | The error is counted, the company's state is left untouched so that it is due again, the run goes on; five such errors in a row stop the run as failed |
| The run is stopped by the time limit | Nothing is lost; the next run continues with what is still due |
| Exclusions cannot be read at the start | The run stops before visiting any site |

## 11. Tests

All with the in-memory store and a fake fetcher, no network:

- the order and the cap of the companies picked;
- each row of the table of section 6, including the third `unreachable`;
- replacement: a person present at the first reading and absent at the
  second is gone;
- exclusions: company never visited; person and their personal address
  dropped; the key equals a pinned value;
- rows of companies without a recent round are deleted;
- the run summary holds numbers only, and nothing printed by `run` or
  `status` contains a name or an address;
- the Supabase store: the shape of the rows it sends, with a fake client,
  as the ingestion's store is tested.

The SQL functions are checked once by the owner in the SQL editor, on an
invented company row, since no test reaches the database.

## 12. Open point for the owner

Removal was agreed as "a command launched from GitHub". Section 7 changes
the place to the Supabase SQL editor, because the public repository makes
workflow inputs public. The owner's action stays one line to run by hand.
To be confirmed when approving this document.

## 13. Left to the builder

Names of helper functions, batch sizes, the exact SQL of the due-companies
query, and how the Supabase store pages through results.

## 14. Consequences for the parent spec

Section 6.1 of `2026-11-11-kaltstart-design.md`: the `contacts` row becomes
`contact_emails` and `contact_people`, the scraping state columns are those
of section 5.1, and `contact_exclusions` and `contact_runs` are added.
