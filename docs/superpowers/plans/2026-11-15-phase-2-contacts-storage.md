# Contact Storage and Nightly Contact Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every night the contact scraper reads the sites of the eligible companies and stores addresses and suggested people in Supabase, with removal on request.

**Architecture:** A `ContactStore` protocol with an in-memory store for tests and a Supabase store for real runs, as the ingestion does. `nightly.run` picks the due companies in Python, calls the existing `scrape_company`, applies exclusions and writes rows and state after each company. A separate GitHub workflow runs it; removal is two SQL functions run by the owner in the Supabase SQL editor.

**Tech Stack:** Python 3.12+, httpx, BeautifulSoup, supabase-py, pytest, GitHub Actions, PostgreSQL (Supabase).

**Spec:** `docs/superpowers/specs/2026-11-15-phase-2-contacts-storage-design.md`

## Global Constraints

- The repository is public and so are its GitHub Actions logs: nothing printed, logged, raised or written to `contact_runs` may contain a person's name, an email address or a page URL. Counts and company ids only.
- No test makes a network call. Tests use `InMemoryContactStore`, a fake fetcher and a fake Supabase client.
- Test first: each test is written and seen failing before the code.
- Fixtures use invented people on `example.ch`, `example.de`, `example.com`. No real name, address or page in the repository.
- Scraper rules are untouched: `scrape_company`, `SiteFetcher` and their limits are used as they are.
- No credentials locally: database commands run in GitHub Actions, the migration and the exclusion functions in the Supabase SQL editor.
- Everything in the repository is in English. Commit format `type: description`, author Camil Mechta, no co-author line.
- Values fixed by the spec: reread after 30 days, retry `unreachable` after 7 days, rows deleted at the 3rd `unreachable` in a row, recent round within 365 days, default cap 300 companies per run, default country `Switzerland`, 5 database write errors in a row stop the run, schedule `17 3 * * *`, job timeout 180 minutes.
- Update `DECISIONS.md` and `CHANGELOG.md` (last task).

## Review Focus

1. A run stopped half-way (time limit, crash): the companies already read keep their rows and state, and the next run does not read them again. Test in Task 3.
2. A company whose reading succeeds with people but no address: people are stored, outcome is the failure cause, next attempt in 30 days. Test in Task 3.
3. A name written with other capitals or extra spaces in the exclusion request than on the site: still excluded. Test in Task 1.
4. A company that was read fine, then becomes unreachable: rows stay for two failures and are deleted at the third. Test in Task 3.
5. An excluded person whose personal address is on the site: the address is dropped with the person, the company's generic address stays. Test in Task 1.

---

### Task 1: Exclusion keys and filtering

**Files:**
- Create: `src/kaltstart/contacts/exclusions.py`
- Test: `tests/contacts/test_exclusions.py`

**Interfaces:**
- Consumes: `CompanyResult`, `FoundEmail`, `FoundPerson` from `kaltstart.contacts.models`; `_owner` from `kaltstart.contacts.selection` (rename it to `owner` in `selection.py` and update its callers, since it is now used from another module).
- Produces:
  - `normalise_name(name: str) -> str`: trimmed, inner whitespace collapsed to one space, lower case.
  - `person_key(company_id: str, name: str) -> str`: SHA-256 hex of `f"{company_id}\n{normalise_name(name)}"` in UTF-8.
  - `without_excluded(result: CompanyResult, person_keys: frozenset[str]) -> tuple[tuple[FoundEmail, ...], tuple[FoundPerson, ...]]`: the emails and people of `result` minus the excluded people and minus the `personal` addresses that `owner` attributes to an excluded person.

- [ ] **Step 1: Write the failing tests**

```python
def test_person_key_is_pinned():
    assert person_key("c1", "Anna Muster") == (
        "85b0bacf71f2773b11e3eb7f94be447720c15f4cc440166dcb416ec15f682f6b")

@pytest.mark.parametrize("name", ["anna muster", "  Anna   Muster ", "ANNA MUSTER"])
def test_person_key_ignores_case_and_spacing(name):
    assert person_key("c1", name) == person_key("c1", "Anna Muster")

def test_person_key_depends_on_the_company():
    assert person_key("c1", "Anna Muster") != person_key("c2", "Anna Muster")

def test_excluded_person_and_their_address_are_dropped():
    # result: people Anna Muster (Founder) and Ben Probe (CTO); emails
    # anna.muster@example.ch (personal), ben@example.ch (personal), info@example.ch (generic)
    emails, people = without_excluded(result, frozenset({person_key("c1", "Anna Muster")}))
    assert [p.name for p in people] == ["Ben Probe"]
    assert [e.address for e in emails] == ["ben@example.ch", "info@example.ch"]

def test_nothing_excluded_returns_everything():
    emails, people = without_excluded(result, frozenset())
    assert (emails, people) == (result.emails, result.people)
```

- [ ] **Step 2: Run** `pytest tests/contacts/test_exclusions.py -q`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement the three functions** in `exclusions.py`; rename `_owner` to `owner`.
- [ ] **Step 4: Run** `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: exclusion keys and filtering for contacts`.

### Task 2: Contact store protocol and in-memory store

**Files:**
- Create: `src/kaltstart/contacts/store.py`
- Test: `tests/contacts/test_store.py`

**Interfaces:**
- Produces `ContactStore` (a `typing.Protocol`) and `InMemoryContactStore` with:
  - `candidate_companies(country: str) -> list[dict]`: companies of that country with a website. Keys: `id`, `name`, `website`, `created_at`, `contacts_checked_at`, `contacts_outcome`, `contacts_attempts`, `contacts_next_at` (ISO strings or `None`).
  - `company_ids_with_round_since(cutoff: date) -> set[str]`
  - `company_ids_with_contacts() -> set[str]`: ids present in `contact_emails` or `contact_people`.
  - `company_ids_with_people() -> set[str]`
  - `exclusions() -> list[dict]`: keys `company_id`, `person_key` (`None` for a whole company).
  - `replace_contacts(company_id: str, emails: list[dict], people: list[dict]) -> None`: deletes the company's rows in both tables, then inserts. Email keys: `company_id`, `address`, `type`, `source_url`, `read_at`. People keys: `company_id`, `name`, `title`, `categories` (list), `level`, `source_url`, `read_at`.
  - `delete_contacts(company_ids: list[str]) -> None`
  - `set_contact_state(company_id: str, *, checked_at: str, outcome: str, attempts: int, next_at: str) -> None`
  - `record_contact_run(run: dict) -> None`
- `InMemoryContactStore` also exposes, for tests: `companies` (dict by id), `rounds` (list of `{"company_id", "date"}`), `emails`, `people`, `excluded` (list), `runs` (list), and `add_company(id, name, website, country="Switzerland", created_at=...)`.

- [ ] **Step 1: Write the failing tests**: `candidate_companies` filters on country and on a non-empty website; `replace_contacts` called twice for one company leaves only the second call's rows and does not touch another company's rows; `delete_contacts` empties both tables for the given ids; `set_contact_state` is visible in `candidate_companies`; `company_ids_with_round_since` keeps a round dated on the cutoff and drops one dated the day before.
- [ ] **Step 2: Run** `pytest tests/contacts/test_store.py -q`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** the protocol and the in-memory store.
- [ ] **Step 4: Run** `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: contact store protocol and in-memory store`.

### Task 3: The nightly run

**Files:**
- Create: `src/kaltstart/contacts/nightly.py`
- Test: `tests/contacts/test_nightly.py`

**Interfaces:**
- Consumes: Task 1 and Task 2; `scrape_company(company: dict, fetcher) -> CompanyResult` from `kaltstart.contacts.scrape` (it needs the keys `company_id`, `name`, `website`, `size_category`; pass `"small"` for `size_category`: it only drives the proposed contact, which is not stored).
- Produces:
  - Constants `REREAD_DAYS = 30`, `RETRY_DAYS = 7`, `MAX_UNREACHABLE = 3`, `RECENT_ROUND_DAYS = 365`, `DEFAULT_MAX = 300`, `MAX_WRITE_ERRORS = 5`.
  - `due_companies(candidates: list[dict], recent_ids: set[str], excluded_ids: set[str], now: datetime, limit: int) -> list[dict]`: eligible and due, never-visited first by `created_at`, then by `contacts_next_at` oldest first, cut at `limit`.
  - `next_state(outcome: str, attempts: int, now: datetime) -> tuple[int, datetime, str]`: new attempts, next attempt, and what to do with the rows: `"replace"`, `"keep"` or `"delete"`.
  - `run(store: ContactStore, fetcher, *, country: str = "Switzerland", limit: int = DEFAULT_MAX, now: datetime | None = None) -> dict`: the run row (`started_at`, `finished_at`, `status`, `country`, `companies_visited`, `with_address`, `with_people`, `outcomes`, `error`), also passed to `store.record_contact_run`, including when the run fails.

- [ ] **Step 1: Write the failing tests for `next_state`**

```python
NOW = datetime(2026, 11, 15, 3, 17, tzinfo=timezone.utc)

@pytest.mark.parametrize("outcome", ["ok", "no_address", "contact_form_only",
    "other_domain_only", "little_text", "not_own_site", "robots_forbidden"])
def test_a_site_that_was_read_is_due_in_30_days(outcome):
    assert next_state(outcome, 2, NOW) == (0, NOW + timedelta(days=30), "replace")

def test_unreachable_is_retried_after_7_days_and_keeps_rows():
    assert next_state("unreachable", 0, NOW) == (1, NOW + timedelta(days=7), "keep")
    assert next_state("unreachable", 1, NOW) == (2, NOW + timedelta(days=7), "keep")

def test_third_unreachable_deletes_rows_and_waits_30_days():
    assert next_state("unreachable", 2, NOW) == (0, NOW + timedelta(days=30), "delete")
```

- [ ] **Step 2: Write the failing tests for `due_companies`**: a company without a recent round, or in `excluded_ids`, is never returned; a company whose `contacts_next_at` is in the future is not due; order is never-visited (oldest `created_at` first) then overdue (oldest `contacts_next_at` first); `limit` cuts the list.
- [ ] **Step 3: Write the failing tests for `run`**, with a fake fetcher that maps a website to a `FetchOutcome` built from invented pages:
  - first run on two companies: rows written for both, state set, run row has `companies_visited == 2` and `outcomes` counts per outcome;
  - a person present at the first run and absent from the page at a run 31 days later is gone from `store.people`;
  - people without an address: people rows exist, `contacts_outcome == "no_address"`, next attempt 30 days later (Review Focus 2);
  - read fine, then `unreachable` three runs in a row 8 days apart: rows still there after the first two, gone after the third (Review Focus 4);
  - an excluded company is never passed to the fetcher; an excluded person is not stored (Review Focus 5 is in Task 1);
  - rows of a company whose only round is 400 days old are deleted at the start of the run, and rows of an excluded company too;
  - a second run started at the same `now` visits nothing (Review Focus 1); and a store whose `replace_contacts` raises on the second of three companies leaves the first company stored, the second with untouched state, and the third stored;
  - `replace_contacts` raising 5 times in a row: the run stops, `status == "failed"`, the run is recorded, `error` holds the exception's class name only;
  - `store.exclusions` raising: no site is visited and the run is recorded as failed;
  - `repr` of the recorded run row contains none of the invented names or addresses.
- [ ] **Step 4: Run** `pytest tests/contacts/test_nightly.py -q`. Expected: FAIL, module not found.
- [ ] **Step 5: Implement `nightly.py`.** `read_at` and `checked_at` are `now.isoformat()`. `with_address` counts outcomes `ok`; `with_people` counts companies with at least one person stored in this run. The state is written right after each company's rows.
- [ ] **Step 6: Run** `pytest -q`. Expected: all pass.
- [ ] **Step 7: Commit** `feat: nightly contact run`.

### Task 4: Supabase contact store

**Files:**
- Create: `src/kaltstart/contacts/supabase_store.py`
- Test: `tests/contacts/test_supabase_store.py`

**Interfaces:**
- Consumes: the `ContactStore` protocol of Task 2. Follow `src/kaltstart/ingestion/supabase_store.py` and its test `tests/ingestion/test_supabase_store.py` (fake client recording calls, paging past 1000 rows, write batches of 500, deletes by batches of 100 ids).
- Produces: `SupabaseContactStore(client)` with `from_env()` reading `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`, raising `RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")` when one is missing.

- [ ] **Step 1: Write the failing tests** with a fake client: `candidate_companies` selects the eight columns of Task 2, filters `country` equal and `website` not null, and pages past 1000 rows; `replace_contacts` sends a delete on `contact_emails` and on `contact_people` filtered on the company id, then one insert per non-empty list; `delete_contacts` batches ids by 100; `set_contact_state` updates the four `contacts_*` columns of one company; `company_ids_with_round_since` filters `date >= cutoff`; `record_contact_run` inserts the row unchanged; `from_env` without variables raises.
- [ ] **Step 2: Run** `pytest tests/contacts/test_supabase_store.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: supabase contact store`.

### Task 5: Commands `run` and `status`

**Files:**
- Modify: `src/kaltstart/contacts/__main__.py`
- Test: `tests/contacts/test_cli.py`

**Interfaces:**
- Consumes: `nightly.run`, `nightly.due_companies`, `SupabaseContactStore.from_env`, `SiteFetcher(default_http_client())`.
- Produces: `main(argv, *, fetcher=None, store=None) -> int` (the `store` parameter is new, for tests).
  - `run [--country Switzerland] [--max 300]`: prints `Visited N, with an address N, with people N`, then one `outcome: count` line per outcome; returns 1 when the run's status is `failed`.
  - `status [--country Switzerland]`: prints `Eligible: N`, `Visited: N`, `With an address: N`, `With people: N`, `Due now: N`, then one line per outcome.

- [ ] **Step 1: Write the failing tests**: `run` with an in-memory store and a fake fetcher returns 0 and prints the three counts; `run --max 1` visits one company; `status` prints the five lines for a store with one visited and one never-visited company; a failed run returns 1; the captured output of both commands contains no invented name and no `@`.
- [ ] **Step 2: Run** `pytest tests/contacts/test_cli.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the two subcommands.
- [ ] **Step 4: Run** `pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: run and status commands for contacts`.

### Task 6: Migration, workflow and documents

**Files:**
- Create: `supabase/migrations/0002_contacts.sql`
- Create: `.github/workflows/contacts.yml`
- Modify: `docs/superpowers/specs/2026-11-11-kaltstart-design.md` (section 6.1, as section 14 of the spec says), `README.md`, `CLAUDE.md` (commands and structure), `DECISIONS.md`, `CHANGELOG.md`
- Test: `tests/contacts/test_migration.py`

**Interfaces:**
- Consumes: the table and column names of spec section 5 and of Task 2.
- Produces: SQL functions `exclude_company(p_company_id text) returns void` and `exclude_person(p_company_id text, p_person_name text) returns void`.

- [ ] **Step 1: Write the failing test** that reads the migration file as text and checks it creates `contact_emails`, `contact_people`, `contact_exclusions`, `contact_runs`, adds the four `contacts_*` columns to `companies`, enables row level security on the four new tables, creates no policy, and defines both functions.
- [ ] **Step 2: Run** `pytest tests/contacts/test_migration.py -q`. Expected: FAIL, file not found.
- [ ] **Step 3: Write the migration.** Tables and keys exactly as spec section 5. The person key in SQL:

```sql
encode(sha256(convert_to(
  p_company_id || E'\n' || lower(regexp_replace(btrim(p_person_name), '\s+', ' ', 'g')),
  'UTF8')), 'hex')
```

`exclude_person` inserts the exclusion (doing nothing when it exists), deletes the row of `contact_people` whose key computed from `name` equals it, and deletes the `personal` rows of `contact_emails` of that company whose local part, split on `.`, `_` and `-`, contains the lower-case last word of the name. `exclude_company` inserts the exclusion with a null `person_key` and deletes the company's rows in both tables. Both functions are `security definer` with `revoke all ... from public`.

- [ ] **Step 4: Write `contacts.yml`**: `schedule: cron "17 3 * * *"`; `workflow_dispatch` with `command` (choice `run`, `status`; default `run`) and `args` (string, default empty); `permissions: contents: read`; `concurrency: group: contacts, cancel-in-progress: false`; one job, `ubuntu-latest`, `timeout-minutes: 180`, checkout, Python 3.12, `pip install -e .`, then `python -m kaltstart.contacts "$COMMAND" $ARGS` with the two secrets, `COMMAND` defaulting to `run`.
- [ ] **Step 5: Update the documents.** README: a "Contacts" section with the two commands and a "Removal on request" section (find the company's `id` in the `companies` table, then the two `select` lines, with an invented example). Decision log: one row for this plan's choices (two tables, replace at each reading, hashed exclusion key, SQL editor instead of a workflow input, Switzerland only).
- [ ] **Step 6: Run** `pytest -q`. Expected: all pass.
- [ ] **Step 7: Commit** `feat: contacts migration, workflow and documentation`.

### Task 7: Go live, with the owner

No code. Each step needs the owner.

- [ ] **Step 1:** Ask the owner's approval, then push `main`.
- [ ] **Step 2:** The owner pastes the content of `supabase/migrations/0002_contacts.sql` into the Supabase SQL editor and runs it.
- [ ] **Step 3:** The owner runs this check in the SQL editor; the expected result is `85b0bacf71f2773b11e3eb7f94be447720c15f4cc440166dcb416ec15f682f6b`, the value pinned in Task 1:

```sql
select encode(sha256(convert_to('c1' || E'\n' || lower(regexp_replace(btrim('  Anna   MUSTER '), '\s+', ' ', 'g')), 'UTF8')), 'hex');
```

- [ ] **Step 4:** `gh workflow run contacts -f command=status`. Expected: eligible about 245, visited 0.
- [ ] **Step 5:** `gh workflow run contacts -f command=run -f args="--max 20"`. Read the log: 20 visited, counts only, no name or address anywhere in the log.
- [ ] **Step 6:** With the owner's go-ahead, `gh workflow run contacts -f command=run` for the full first pass (90 to 120 minutes), then `status`.
- [ ] **Step 7:** Record the first pass's counts in `DECISIONS.md` and `CHANGELOG.md`, commit `docs: first full contact run`, push with the owner's approval.
