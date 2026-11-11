# Phase 1: Tech.eu ingestion — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status note:** Tasks 1 to 7 were executed on 2026-11-11. Where the implementation departs from this plan, the decision is recorded in `DECISIONS.md` (D16 to D19). Task 8 is still to do.

**Goal:** Fetch Tech.eu funding rounds for Switzerland, Germany and Austria, clean them, store them in Supabase and keep them up to date every night without duplicates.

**Architecture:** An HTTP client talks to the Tech.eu API, pure functions clean the data, a "store" writes to Supabase, and a pipeline chains them. Raw data is kept next to cleaned data, so cleaning can be replayed without calling the API again. The store has an in-memory version for tests: no test touches the network.

**Tech Stack:** Python 3.12+, httpx, supabase-py, pytest, GitHub Actions. Python package `kaltstart` in `src/kaltstart/`.

**Spec:** `docs/superpowers/specs/2026-11-11-kaltstart-design.md`

## Global Constraints

- No call to any AI API at runtime.
- No test makes a real network call; Tech.eu responses are replayed from `tests/fixtures/techeu/`.
- Tech.eu quotas: 120 requests per minute, 600 per hour, 2000 per day. The client waits 7 seconds between two requests (about 514 per hour) and stops at 1500 requests per run.
- Countries covered, exact API spelling: `Switzerland`, `Germany`, `Austria`.
- Source credit in the README: "Tech.eu Funding Explorer", licence CC BY 4.0.
- All repository files are in English: public documents, spec, plans, code, comments and commit messages.
- No secret in the repo: Supabase keys go through environment variables (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
- Test-driven development: the test is written and seen failing before the code.
- At least one commit per task, message in the format `type: description` (`feat`, `test`, `docs`, `chore`, `fix`).

## What the API really returns (verified on 2026-11-11)

`GET /api/v1/rounds?country=&from=&to=&limit=&after=` returns
`{data: [...], nextCursor, count, appliedFilters, ...}`. `nextCursor` is
`null` on the last page. An unknown country returns HTTP 400 with
`{error, hint}`. A round:

```json
{"id": "F9B3...", "pageUrl": "https://funding.tech.eu/deals/F9B3...",
 "date": "2026-11-10", "stage": "Seed", "rawRoundType": "seed",
 "amountEur": 4547887, "amountNative": 5100000, "currency": "USD",
 "company": {"id": "0DF1...", "name": "Light Frame", "country": "Switzerland",
             "pageUrl": "https://funding.tech.eu/companies/light-frame-0df151be",
             "city": "Lausanne", "founded": null, "sectors": ["Fintech"]},
 "investors": ["Rogue Venture Partners", "Tenity "],
 "source": {"domain": "tech.eu", "tier": "own"}, "confidence": "high"}
```

Facts observed on 100 Swiss rounds:

- `amountEur` is already in euros; it is `null` for 27 rounds out of 100, with `currency` equal to `""`.
- Values of `stage`: `Pre-Seed`, `Seed`, `Series A`, `Series B`, `Series C`, `Series D+`, `Growth/Late`, `Grant`, `Debt`, `Other` (53 out of 100).
- `city` can be `null`, `""`, end with a space (`"Zurich "`), or contain a canton (`"Vaud"`, `"Obwalden"`). `"Bern"` and `"Berne"` coexist.
- Investor names can end with a space (`"Tenity "`).

`GET /api/v1/companies/{id}` returns `description`, `website`, `founded`,
`founders` (empty), `sectors`, `rounds`.

`GET /api/v1/changes?since=<date or ISO timestamp>&limit=` returns the rounds
added since `since`, all countries combined, with a `createdAt` field, plus
`removed` (deleted rounds) and `nextCursor`. This response has no
`appliedFilters`: filtering by country is therefore done on our side. Changes
to a round that already exists do not appear there.

Response headers: `ratelimit-limit`, `ratelimit-remaining`, `ratelimit-reset`.

## Review Focus

1. Round without a city, without an amount or without a currency (`null` or `""`): it is stored without error, with `city` and `amount_eur` as `null`. Test in Task 3.
2. Same company in several rounds with different city spellings: a single `companies` row, the most recent round wins. Test in Task 6.
3. The API returns 429 or does not answer in the middle of a pagination: three attempts, then stop; the run is recorded as failed and nothing is marked as successful. Tests in Tasks 4 and 6.
4. The 1500-request budget is reached while fetching company records: clean stop, the next run resumes where it stopped. Test in Task 6.
5. Website missing or malformed in the record (`null`, without `https://`, spaces): normalised or set to `null`, never stored as is. Test in Task 3.

---

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package `kaltstart`, dependencies, pytest configuration |
| `src/kaltstart/ingestion/cleaning.py` | Pure functions: cities, investors, size category, website |
| `src/kaltstart/ingestion/city_aliases.csv` | City mapping table, written by hand |
| `src/kaltstart/ingestion/transform.py` | Turns a raw round into `companies` and `rounds` rows |
| `src/kaltstart/ingestion/techeu_client.py` | HTTP calls: pagination, filter check, rate, retries, budget |
| `src/kaltstart/ingestion/store.py` | `Store` interface and `InMemoryStore` for tests |
| `src/kaltstart/ingestion/supabase_store.py` | `SupabaseStore`, same interface, writes to Supabase |
| `src/kaltstart/ingestion/pipeline.py` | Sequences: `backfill`, `sync_changes`, `fetch_company_details`, `reclean` |
| `src/kaltstart/ingestion/__main__.py` | Command line `python -m kaltstart.ingestion <command>` |
| `supabase/migrations/0001_ingestion.sql` | Table creation |
| `.github/workflows/tests.yml` | Runs pytest on every push |
| `.github/workflows/nightly.yml` | Runs the synchronisation every night |
| `tests/ingestion/` | One test file per module |
| `tests/fixtures/techeu/` | Recorded real API responses |

Shape of the rows exchanged between modules (Python dictionaries):

```python
CompanyRow = {"id": str, "name": str, "country": str, "city_raw": str | None,
              "city": str | None, "region": str | None, "sectors": list[str],
              "techeu_url": str}
RoundRow = {"id": str, "company_id": str, "date": str, "stage": str | None,
            "raw_round_type": str | None, "amount_eur": int | None,
            "amount_native": float | None, "currency": str | None,
            "size_category": str, "investors": list[str], "source_url": str,
            "source_domain": str | None, "confidence": str | None}
CompanyDetails = {"website": str | None, "description": str | None,
                  "founded": int | None}
```

---

### Task 1: project skeleton and public documents

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/kaltstart/__init__.py`, `src/kaltstart/ingestion/__init__.py`, `tests/__init__.py`, `tests/ingestion/__init__.py`, `tests/test_smoke.py`
- Create: `README.md`, `PRD.md`, `DECISIONS.md`, `CHANGELOG.md`, `CLAUDE.md`
- Create: `.github/workflows/tests.yml`
- Create: `tests/fixtures/techeu/rounds_page1.json`, `rounds_page2.json`, `company.json`, `changes.json`

**Interfaces:**
- Produces: importable package `kaltstart`; `pytest` command; fixtures. `rounds_page1.json` contains 3 rounds and a non-null `nextCursor`, `rounds_page2.json` contains 2 rounds and `nextCursor: null`, both with `appliedFilters` equal to `{"country": "Switzerland", "from": "2026-09-01", "to": "2026-11-10"}`. `changes.json` contains at least one Swiss round, one British round, and `removed: []`.

- [ ] **Step 1:** write `tests/test_smoke.py`

```python
def test_package_imports():
    import kaltstart.ingestion  # noqa: F401
```

- [ ] **Step 2:** run `pytest -q`. Expected: failure, `ModuleNotFoundError: kaltstart`.
- [ ] **Step 3:** create `pyproject.toml` (name `kaltstart`, `requires-python = ">=3.12"`, dependencies `httpx`, `supabase`; `dev` extra with `pytest`; packages under `src/`; `[tool.pytest.ini_options] testpaths = ["tests"]`), the `__init__.py` files, then `pip install -e ".[dev]"`.
- [ ] **Step 4:** run `pytest -q`. Expected: `1 passed`.
- [ ] **Step 5:** create `.gitignore` (`.env`, `__pycache__/`, `.venv/`, `*.egg-info/`, `.pytest_cache/`) and `.env.example` (`SUPABASE_URL=`, `SUPABASE_SERVICE_KEY=`, without values).
- [ ] **Step 6:** record the fixtures from real API responses (4 requests at most), reducing them to the size given in "Produces".
- [ ] **Step 7:** write the public documents, in English:
  - `PRD.md`: problem, users, journey, scope and out of scope, metrics and thresholds, phases. Content taken from sections 1 to 4 and 10 of the spec.
  - `DECISIONS.md`: D1 to D13 from the spec, plus D14 (package `src/kaltstart/` instead of `src/ingestion/` directly: a single package name avoids import conflicts) and D15 (nightly synchronisation through `/changes`: it is the mechanism the API provides, and it also reports deletions).
  - `CHANGELOG.md`: "Keep a Changelog" format, one `Phase 0` entry.
  - `CLAUDE.md`: commands (`pip install -e ".[dev]"`, `pytest -q`), the global constraints above, the folder structure, the rule "update DECISIONS.md and CHANGELOG.md with every notable change".
  - `README.md`: three-sentence description, project status by phase, installation, mention "Data: Tech.eu Funding Explorer, CC BY 4.0".
- [ ] **Step 8:** create `.github/workflows/tests.yml`: on `push` and `pull_request`, Python 3.12, `pip install -e ".[dev]"`, `pytest -q`.
- [ ] **Step 9:** commit `chore: scaffold project, public docs and CI`.

### Task 2: cleaning functions

**Files:**
- Create: `src/kaltstart/ingestion/cleaning.py`, `src/kaltstart/ingestion/city_aliases.csv`
- Test: `tests/ingestion/test_cleaning.py`

**Interfaces:**
- Produces:
  - `clean_city(raw: str | None) -> tuple[str | None, str | None]` returns `(city, region)`.
  - `clean_investors(raw: list[str] | None) -> list[str]`
  - `size_category(stage: str | None, amount_eur: int | None) -> str` returns `"small"`, `"medium"` or `"large"`.
  - `clean_website(raw: str | None) -> str | None`
  - Constants `SMALL_MAX_EUR = 3_000_000` and `MEDIUM_MAX_EUR = 15_000_000`.

- [ ] **Step 1:** write the tests

```python
import pytest
from kaltstart.ingestion.cleaning import (
    clean_city, clean_investors, clean_website, size_category)

@pytest.mark.parametrize("raw,expected", [
    ("Zurich ", ("Zurich", None)),
    ("  Zürich", ("Zurich", None)),
    ("Berne", ("Bern", None)),
    ("Vaud", (None, "Vaud")),
    ("Obwalden", (None, "Obwalden")),
    ("St.  Gallen", ("St. Gallen", None)),
    ("Eggersriet", ("Eggersriet", None)),   # unknown: kept as is
    ("", (None, None)),
    (None, (None, None)),
])
def test_clean_city(raw, expected):
    assert clean_city(raw) == expected

def test_clean_investors_strips_and_dedupes_keeping_order():
    assert clean_investors(["Tenity ", "Altair Capital", "Tenity", ""]) == [
        "Tenity", "Altair Capital"]
    assert clean_investors(None) == []

@pytest.mark.parametrize("stage,amount,expected", [
    ("Pre-Seed", 50_000_000, "small"),      # a known stage wins
    ("Seed", None, "small"),
    ("Series A", None, "medium"),
    ("Series B", 1_000_000, "large"),
    ("Series C", None, "large"),
    ("Series D+", None, "large"),
    ("Growth/Late", None, "large"),
    ("Other", 2_999_999, "small"),
    ("Other", 3_000_000, "medium"),
    ("Other", 15_000_000, "medium"),
    ("Other", 15_000_001, "large"),
    ("Grant", 150_000, "small"),            # Grant and Debt: by amount
    ("Debt", 20_000_000, "large"),
    ("Other", None, "small"),               # neither stage nor amount
    (None, None, "small"),
    ("Brand New Stage", 5_000_000, "medium"),
])
def test_size_category(stage, amount, expected):
    assert size_category(stage, amount) == expected

@pytest.mark.parametrize("raw,expected", [
    ("https://www.lightframe.tech/", "https://www.lightframe.tech"),
    (" www.example.ch ", "https://www.example.ch"),
    ("http://example.de/path", "http://example.de/path"),
    ("", None), (None, None), ("not a url", None),
])
def test_clean_website(raw, expected):
    assert clean_website(raw) == expected
```

- [ ] **Step 2:** run `pytest tests/ingestion/test_cleaning.py -q`. Expected: failure at import.
- [ ] **Step 3:** create `city_aliases.csv` with the columns `raw,city,region`. The `raw` column is compared case-insensitively. Starting rows — variants: Zürich→Zurich, Berne→Bern, Genève→Geneva, Genf→Geneva, Luzern→Lucerne, Basle→Basel, München→Munich, Köln→Cologne, Nürnberg→Nuremberg, Wien→Vienna. Regions (empty `city` column): Vaud, Obwalden, Bavaria, Bayern, Baden-Württemberg, North Rhine-Westphalia, Hesse, Tyrol, Styria.
- [ ] **Step 4:** implement the four functions. `clean_city`: replaces runs of spaces with a single one, strips the edges, then looks up the table; a value absent from the table is returned as a city. `clean_website`: strips spaces and the trailing `/`, adds `https://` if there is no scheme, returns `None` if the result contains a space or has no dot in the host name.
- [ ] **Step 5:** run `pytest tests/ingestion/test_cleaning.py -q`. Expected: all pass.
- [ ] **Step 6:** commit `feat: add cleaning rules for cities, investors, size and websites`.

### Task 3: transforming a raw round

**Files:**
- Create: `src/kaltstart/ingestion/transform.py`
- Test: `tests/ingestion/test_transform.py`

**Interfaces:**
- Consumes: the functions of `cleaning.py`.
- Produces:
  - `transform_round(raw: dict) -> tuple[CompanyRow, RoundRow]`
  - `transform_company_details(raw: dict) -> CompanyDetails`

- [ ] **Step 1:** write the tests

```python
import json, pathlib
from kaltstart.ingestion.transform import transform_round, transform_company_details

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "techeu"

def _round(**overrides):
    raw = json.loads((FIX / "rounds_page1.json").read_text())["data"][0]
    raw.update(overrides)
    return raw

def test_transform_round_maps_all_fields():
    raw = _round()
    company, rnd = transform_round(raw)
    assert company == {
        "id": raw["company"]["id"], "name": raw["company"]["name"],
        "country": "Switzerland", "city_raw": raw["company"]["city"],
        "city": "Lausanne", "region": None,
        "sectors": raw["company"]["sectors"],
        "techeu_url": raw["company"]["pageUrl"]}
    assert rnd["id"] == raw["id"]
    assert rnd["company_id"] == raw["company"]["id"]
    assert rnd["date"] == raw["date"]
    assert rnd["amount_eur"] == raw["amountEur"]
    assert rnd["size_category"] == "small"
    assert rnd["source_url"] == raw["pageUrl"]
    assert rnd["source_domain"] == raw["source"]["domain"]
    assert all(name == name.strip() for name in rnd["investors"])

def test_missing_amount_city_and_currency_become_none():
    raw = _round(amountEur=None, amountNative=None, currency="", fx=None)
    raw["company"] = {**raw["company"], "city": None, "sectors": None}
    company, rnd = transform_round(raw)
    assert (company["city"], company["region"], company["sectors"]) == (None, None, [])
    assert (rnd["amount_eur"], rnd["currency"]) == (None, None)

def test_missing_source_and_investors():
    company, rnd = transform_round(_round(source=None, investors=None))
    assert rnd["source_domain"] is None and rnd["investors"] == []

def test_company_details():
    raw = json.loads((FIX / "company.json").read_text())
    assert transform_company_details(raw) == {
        "website": "https://www.lightframe.tech",
        "description": raw["description"], "founded": raw["founded"]}

def test_company_details_with_bad_website_and_blank_description():
    assert transform_company_details(
        {"website": "n/a", "description": "  ", "founded": None}
    ) == {"website": None, "description": None, "founded": None}
```

- [ ] **Step 2:** run `pytest tests/ingestion/test_transform.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement the two functions in `transform.py`. Every empty string becomes `None`.
- [ ] **Step 4:** run again. Expected: all pass.
- [ ] **Step 5:** commit `feat: transform raw Tech.eu rounds into company and round rows`.

### Task 4: Tech.eu client

**Files:**
- Create: `src/kaltstart/ingestion/techeu_client.py`
- Test: `tests/ingestion/test_techeu_client.py`

**Interfaces:**
- Produces:
  - `class TechEuClient(http: httpx.Client, min_interval_s: float = 7.0, max_requests: int = 1500, sleep: Callable[[float], None] = time.sleep)` with the attribute `requests_made: int`.
  - `iter_rounds(country: str, date_from: str, date_to: str) -> Iterator[dict]`
  - `fetch_changes(since: str) -> tuple[list[dict], list[str]]` returns `(added rounds, removed identifiers)`.
  - `get_company(company_id: str) -> dict`
  - Exceptions: `TechEuError`, and its subclasses `FilterMismatchError` and `BudgetExhaustedError`.
  - `BASE_URL = "https://funding.tech.eu/api/v1"`, `PAGE_SIZE = 100`.

The tests build the client with `httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)` and `sleep` replaced by a function that records the durations.

- [ ] **Step 1:** write the tests, one per behaviour:
  - `test_iter_rounds_follows_cursor`: the handler serves `rounds_page1.json` then `rounds_page2.json`; we get 5 rounds; the second request carries `after=<nextCursor of page 1>`; every request carries `country=Switzerland`, `from`, `to`, `limit=100`.
  - `test_filter_mismatch_raises`: the response has `appliedFilters` without `country`; `list(client.iter_rounds(...))` raises `FilterMismatchError` before yielding any round.
  - `test_waits_between_requests`: after two requests, `sleep` was called with a duration between 0 and 7.0; no wait before the first one.
  - `test_retries_then_succeeds`: the handler returns 429, then 503, then 200; the call succeeds; `requests_made == 3`.
  - `test_gives_up_after_three_attempts`: the handler always returns 503; `TechEuError` is raised; exactly 3 requests; same expectation for `httpx.ConnectTimeout`.
  - `test_client_error_is_not_retried`: HTTP 400 with `{"error": "unknown country: Suisse"}` raises `TechEuError` whose message contains that text, after a single request.
  - `test_budget_exhausted`: with `max_requests=2`, the third request raises `BudgetExhaustedError` without calling the handler.
  - `test_fetch_changes_returns_added_and_removed`: serves `changes.json` modified with `removed: ["X1", {"id": "X2"}]`; returns all the rounds of `data` and `["X1", "X2"]`.
  - `test_fetch_changes_stops_on_repeated_cursor`: the handler always returns the same non-null `nextCursor`; the call ends after 2 requests.
- [ ] **Step 2:** run `pytest tests/ingestion/test_techeu_client.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `TechEuClient`. A private method `_get(path, params)` carries the budget, the wait and the retries; the three public methods use it. Wait between attempts: 5, then 15 seconds, passed to `sleep`. We retry on 429, 5xx and `httpx.TransportError`; never on other 4xx. The filter check compares `country`, `from` and `to` of `appliedFilters` with the values sent.
- [ ] **Step 4:** run again. Expected: all pass.
- [ ] **Step 5:** commit `feat: add Tech.eu client with pagination, throttling and retries`.

### Task 5: storage

**Files:**
- Create: `src/kaltstart/ingestion/store.py`, `src/kaltstart/ingestion/supabase_store.py`, `supabase/migrations/0001_ingestion.sql`
- Test: `tests/ingestion/test_store.py`

**Interfaces:**
- Produces: `class Store(Protocol)` with:
  - `upsert_raw_rounds(raws: list[dict]) -> None` (key: `raw["id"]`)
  - `upsert_companies(rows: list[CompanyRow]) -> None`
  - `upsert_rounds(rows: list[RoundRow]) -> None`
  - `delete_rounds(ids: list[str]) -> int` (also deletes from `raw_rounds`)
  - `all_raw_rounds() -> list[dict]`
  - `company_ids_missing_details(limit: int) -> list[str]`
  - `set_company_details(company_id: str, details: CompanyDetails) -> None`
  - `last_successful_run_started_at() -> str | None` (ISO timestamp)
  - `record_run(run: dict) -> None`
  - `counts() -> dict[str, int]` with the keys `raw_rounds`, `companies`, `rounds`
  - `all_rounds_with_company() -> list[dict]`: each element is a `RoundRow` with a `company` key containing its `CompanyRow`
- `InMemoryStore` and `SupabaseStore(client: supabase.Client)` implement `Store`.
- `SupabaseStore.from_env() -> SupabaseStore` reads `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`, and raises `RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")` if one is missing.

- [ ] **Step 1:** write the tests of `InMemoryStore`:
  - inserting the same round twice creates only one row, and the second version replaces the first;
  - `upsert_companies` on a company whose record is already filled keeps `website`, `description`, `founded` and `details_fetched_at`;
  - `company_ids_missing_details(limit=2)` returns at most 2 identifiers, only those without `details_fetched_at`; after `set_company_details`, the company no longer appears, even if `website` is `None`;
  - `delete_rounds(["a", "unknown"])` returns 1 and removes `a` from `rounds` and from `raw_rounds`;
  - `all_rounds_with_company()` returns one entry per round, with the row of its company under the key `company`;
  - `last_successful_run_started_at()` returns `None` without a run, ignores `failed` runs, and returns the most recent `started_at` among the `success` ones;
  - `SupabaseStore.from_env()` raises `RuntimeError` when the variables are absent (with `monkeypatch.delenv`).
- [ ] **Step 2:** run `pytest tests/ingestion/test_store.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `Store` and `InMemoryStore` in `store.py`.
- [ ] **Step 4:** run again. Expected: all pass except the `from_env` test.
- [ ] **Step 5:** write `supabase/migrations/0001_ingestion.sql`:

```sql
create table raw_rounds (
  id text primary key,
  payload jsonb not null,
  fetched_at timestamptz not null default now()
);
create table companies (
  id text primary key,
  name text not null,
  country text not null,
  city_raw text,
  city text,
  region text,
  sectors text[] not null default '{}',
  techeu_url text not null,
  website text,
  description text,
  founded int,
  details_fetched_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table rounds (
  id text primary key,
  company_id text not null references companies(id),
  date date not null,
  stage text,
  raw_round_type text,
  amount_eur bigint,
  amount_native numeric,
  currency text,
  size_category text not null check (size_category in ('small','medium','large')),
  investors text[] not null default '{}',
  source_url text not null,
  source_domain text,
  confidence text,
  updated_at timestamptz not null default now()
);
create index rounds_date_idx on rounds (date desc);
create index rounds_company_idx on rounds (company_id);
create index companies_country_city_idx on companies (country, city);
create table sync_runs (
  id bigint generated always as identity primary key,
  command text not null,
  started_at timestamptz not null,
  finished_at timestamptz not null,
  status text not null check (status in ('success','failed')),
  rounds_upserted int not null default 0,
  rounds_removed int not null default 0,
  companies_upserted int not null default 0,
  details_fetched int not null default 0,
  requests_made int not null default 0,
  error text
);
alter table raw_rounds enable row level security;
alter table companies enable row level security;
alter table rounds enable row level security;
alter table sync_runs enable row level security;
```

  No access policy is created: only the service key, used by the scripts, can read and write. Read policies for students will come in Phase 4.
- [ ] **Step 6:** implement `SupabaseStore` with `client.table(...).upsert(...)`, in batches of 500 rows. `upsert_companies` sends only the columns of `CompanyRow` plus `updated_at`, so as not to overwrite the record.
- [ ] **Step 7:** run `pytest tests/ingestion/test_store.py -q` again. Expected: all pass.
- [ ] **Step 8:** commit `feat: add store interface, in-memory store, Supabase store and schema`.

`SupabaseStore` has no automatic test beyond `from_env`: it is verified against the real database in Task 8.

### Task 6: pipeline

**Files:**
- Create: `src/kaltstart/ingestion/pipeline.py`
- Test: `tests/ingestion/test_pipeline.py`

**Interfaces:**
- Consumes: `TechEuClient`, `Store`, `transform_round`, `transform_company_details`.
- Produces:
  - `COUNTRIES = ("Switzerland", "Germany", "Austria")`
  - `backfill(client, store, date_from: str, date_to: str) -> dict`
  - `sync_changes(client, store) -> dict`
  - `fetch_company_details(client, store, limit: int = 1000) -> dict`
  - `reclean(store) -> dict`
  - Each function returns the run dictionary, of the same shape as the columns of `sync_runs` (without `id`), and records it with `store.record_run`, including on failure; in that case `status` is `"failed"`, `error` contains the message, and the exception is re-raised.

The tests use `InMemoryStore` and a fake client (a test class with the same three methods and `requests_made`).

- [ ] **Step 1:** write the tests:
  - `test_backfill_stores_raw_companies_and_rounds`: 3 rounds for 2 companies give `counts() == {"raw_rounds": 3, "companies": 2, "rounds": 3}`; `iter_rounds` was called once per country of `COUNTRIES`; the run is `success` with `rounds_upserted == 3`.
  - `test_backfill_twice_adds_nothing`: two identical calls leave the same `counts()`.
  - `test_company_city_comes_from_latest_round`: two rounds of the same company, city `"Zurich "` on 2026-01-10 and `"Vaud"` on 2026-06-01, in both arrival orders: the `companies` row has `city is None` and `region == "Vaud"`.
  - `test_sync_changes_keeps_only_our_countries`: `fetch_changes` returns a Swiss round, a British round, and `["old-id"]` to remove; only the Swiss one is stored, and `rounds_removed` is the number actually removed.
  - `test_sync_changes_since_is_last_success_minus_one_day`: with a last successful run at `2026-11-10T03:00:00+00:00`, `fetch_changes` receives `"2026-11-09T03:00:00+00:00"`.
  - `test_sync_changes_without_previous_run_fails_clearly`: raises `RuntimeError("no successful run found: run backfill first")`.
  - `test_failure_is_recorded_and_reraised`: `iter_rounds` raises `TechEuError` on the second country; the exception propagates; a `failed` run is recorded; `last_successful_run_started_at()` stays `None`.
  - `test_fetch_company_details_fills_and_resumes`: 3 companies without a record; the fake client raises `BudgetExhaustedError` on the second call; the run is `success` with `details_fetched == 1`; a second call handles the 2 remaining.
  - `test_reclean_reapplies_rules_without_client`: we store a raw round, modify its `rounds` row by hand (`size_category="large"`), and `reclean(store)` puts it back to `"small"`.
- [ ] **Step 2:** run `pytest tests/ingestion/test_pipeline.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement the four functions. A private function `_store_rounds(store, raws) -> tuple[int, int]` is shared by `backfill`, `sync_changes` and `reclean`: it writes the raw rounds, then the companies (one row per company, taken from its most recent round in the batch), then the rounds. In `fetch_company_details`, `BudgetExhaustedError` stops the loop without failing the run; any other `TechEuError` on a company is counted and we move to the next one.
- [ ] **Step 4:** run again. Expected: all pass.
- [ ] **Step 5:** commit `feat: add backfill, incremental sync, details fetch and reclean pipelines`.

### Task 7: command line and nightly run

**Files:**
- Create: `src/kaltstart/ingestion/__main__.py`, `.github/workflows/nightly.yml`
- Test: `tests/ingestion/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `main(argv: list[str], *, client=None, store=None) -> int`, and the commands:
  - `backfill [--months 12]`: `backfill` over the period, then `fetch_company_details`.
  - `sync`: `sync_changes`, then `fetch_company_details`.
  - `reclean`: `reclean`.
  - `report`: prints, without calling the API, the `counts()`, the number of rounds per country, the stage × size category table, and for rounds whose stage is known the median of `amount_eur` per stage.
  - `cities`: prints each distinct value of `city` with its country and its number of companies, sorted by country then by descending count, then the list of `city_raw` values that differ from `city`.

- [ ] **Step 1:** write the tests with `InMemoryStore` and a fake client injected into `main`:
  - `main(["backfill", "--months", "12"])` returns 0, the store contains the rounds, and the output (`capsys`) contains `rounds_upserted`;
  - `main(["sync"])` without a previous run returns 1 and prints `run backfill first` on standard error;
  - `main(["report"])` prints the three counters and one line per size category;
  - `main(["cities"])` prints `Zurich` with its count;
  - `main([])` returns 2.
- [ ] **Step 2:** run `pytest tests/ingestion/test_cli.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `main` with `argparse`. Without a `client` or `store` provided, it builds `TechEuClient(httpx.Client(base_url=BASE_URL, timeout=30))` and `SupabaseStore.from_env()`. `report` and `cities` read the data with `store.all_rounds_with_company()`.
- [ ] **Step 4:** run the whole suite again: `pytest -q`. Expected: everything passes.
- [ ] **Step 5:** create `.github/workflows/nightly.yml`: triggers `schedule` (`cron: "17 2 * * *"`) and `workflow_dispatch` with an input `command` (choice `sync`, `backfill`, `reclean`; default `sync`); Python 3.12; `pip install -e .`; `python -m kaltstart.ingestion <command>`, that is `sync` for the scheduled trigger, with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` taken from the repo secrets; `timeout-minutes: 180`.
- [ ] **Step 6:** commit `feat: add ingestion CLI and nightly workflow`.

### Task 8: go-live and verification on real data

This task requires actions from the project owner: they are marked **[Owner]**.

- [ ] **Step 1 [Owner]:** create a public GitHub repo named `kaltstart`, then push the code to it (`git remote add origin ...`, `git push -u origin main`). Check that the `tests` workflow is green.
- [ ] **Step 2 [Owner]:** create a free Supabase project, Europe region. In the SQL editor, run the content of `supabase/migrations/0001_ingestion.sql`.
- [ ] **Step 3 [Owner]:** copy the project URL and the `service_role` key into the GitHub repo secrets, under the names `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`. Never paste them into a chat or into a file of the repo.
- [ ] **Step 4:** launch the first load from the Actions tab (workflow `nightly`, run by hand with `command=backfill`). Expected duration: about 1 h 30, because of the 7-second wait between company records.
- [ ] **Step 5:** check with `report`: `rounds` is about 830 (260 for Switzerland, 503 for Germany, 63 for Austria, give or take a few depending on the date); no `rounds` row without `size_category`.
- [ ] **Step 6:** run `sync` twice in a row. Expected: the second run has `rounds_upserted` equal to the number of rounds added by Tech.eu in the last 24 hours (a few at most) and `counts()` does not change between the two, apart from real additions.
- [ ] **Step 7:** calibrate the size bounds. Read in `report` the median of `amount_eur` for `Seed`, `Series A` and `Series B`. If the `Series A` median falls outside the 3 to 15 million euro range, or if the `Seed` median exceeds 3 million, propose new bounds to the project owner, change `SMALL_MAX_EUR` and `MEDIUM_MAX_EUR` and the corresponding tests, then run `reclean`. Record the result in `DECISIONS.md`, whether the bounds change or not.
- [ ] **Step 8:** clean the cities. Run `cities`, submit the suspicious values to the project owner (regions, spelling variants), complete `city_aliases.csv`, run `reclean`, run `cities` again to confirm.
- [ ] **Step 9:** update `CHANGELOG.md` (entry `Phase 1` with the real figures), `README.md` (status of Phase 1, number of rounds and companies, share of companies with a website) and `CLAUDE.md` (command-line commands). Commit `docs: record phase 1 results`.
- [ ] **Step 10:** request a code review of the phase with the skill `superpowers:requesting-code-review`, then address the remarks.
