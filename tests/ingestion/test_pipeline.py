import copy
import json
from pathlib import Path

import pytest

from kaltstart.ingestion.pipeline import (
    COUNTRIES,
    backfill,
    fetch_company_details,
    reclean,
    sync_changes,
)
from kaltstart.ingestion.store import InMemoryStore
from kaltstart.ingestion.techeu_client import BudgetExhaustedError, TechEuError
from kaltstart.ingestion.transform import transform_round

FIXTURES = Path(__file__).parent.parent / "fixtures" / "techeu"
TEMPLATE = json.loads((FIXTURES / "rounds_page1.json").read_text())["data"][0]
COMPANY_PAYLOAD = json.loads((FIXTURES / "company.json").read_text())


def make_raw(round_id, company_id="co-1", date="2026-03-01", country="Switzerland",
             city="Lausanne"):
    raw = copy.deepcopy(TEMPLATE)
    raw["id"] = round_id
    raw["date"] = date
    raw["company"].update(id=company_id, country=country, city=city,
                          name=f"Company {company_id}")
    return raw


class FakeClient:
    """Canned TechEuClient. `fail_at` maps a call number (1-based, per method)
    to the exception raised on that call."""

    def __init__(self, rounds=None, changes=None, companies=None, fail_at=None):
        self.rounds = rounds or {}
        self.changes = changes or ([], [])
        self.companies = companies or {}
        self.fail_at = fail_at or {}
        self.requests_made = 0
        self.calls = {"iter_rounds": [], "fetch_changes": [], "get_company": []}

    def _record(self, method, arg):
        self.calls[method].append(arg)
        self.requests_made += 1
        exc = self.fail_at.get((method, len(self.calls[method])))
        if exc:
            raise exc

    def iter_rounds(self, country, date_from, date_to):
        self._record("iter_rounds", country)
        yield from self.rounds.get(country, [])

    def fetch_changes(self, since):
        self._record("fetch_changes", since)
        return self.changes

    def get_company(self, company_id):
        self._record("get_company", company_id)
        return self.companies.get(company_id, COMPANY_PAYLOAD)


def run_row(status, started_at):
    return {
        "command": "backfill", "started_at": started_at,
        "finished_at": started_at, "status": status, "rounds_upserted": 0,
        "rounds_removed": 0, "companies_upserted": 0, "details_fetched": 0,
        "requests_made": 0, "error": None,
    }


def last_run(store):
    return store._runs[-1]


def test_backfill_stores_raw_companies_and_rounds():
    store = InMemoryStore()
    client = FakeClient(rounds={"Switzerland": [
        make_raw("r1", "co-1"), make_raw("r2", "co-1", date="2026-04-01"),
        make_raw("r3", "co-2")]})
    run = backfill(client, store, "2026-01-01", "2026-12-31")
    assert store.counts() == {"raw_rounds": 3, "companies": 2, "rounds": 3}
    assert client.calls["iter_rounds"] == list(COUNTRIES)
    assert run["status"] == "success"
    assert run["command"] == "backfill"
    assert run["rounds_upserted"] == 3
    assert run["companies_upserted"] == 2
    assert run["requests_made"] == 3
    assert last_run(store) == run


def test_backfill_twice_adds_nothing():
    store = InMemoryStore()
    rounds = {"Germany": [make_raw("r1", country="Germany"), make_raw("r2", "co-2")]}
    backfill(FakeClient(rounds=rounds), store, "2026-01-01", "2026-12-31")
    first = store.counts()
    backfill(FakeClient(rounds=rounds), store, "2026-01-01", "2026-12-31")
    assert store.counts() == first


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_company_city_comes_from_latest_round(order):
    store = InMemoryStore()
    raws = [make_raw("old", date="2026-01-10", city="Zurich "),
            make_raw("new", date="2026-06-01", city="Vaud")]
    client = FakeClient(rounds={"Switzerland": [raws[i] for i in order]})
    backfill(client, store, "2026-01-01", "2026-12-31")
    company = store.all_rounds_with_company()[0]["company"]
    assert company["city"] is None
    assert company["region"] == "Vaud"


def test_sync_changes_keeps_only_our_countries():
    store = InMemoryStore()
    store.upsert_raw_rounds([make_raw("old-id")])
    store.upsert_rounds([_round_row("old-id")])
    store.record_run(run_row("success", "2026-11-10T03:00:00+00:00"))
    client = FakeClient(
        changes=([make_raw("ch", country="Switzerland"),
                  make_raw("uk", "co-uk", country="UK")], ["old-id", "unknown"]))
    run = sync_changes(client, store)
    assert store.counts() == {"raw_rounds": 1, "companies": 1, "rounds": 1}
    assert run["rounds_upserted"] == 1
    assert run["rounds_removed"] == 1
    assert run["status"] == "success"


def _round_row(round_id):
    return transform_round(make_raw(round_id))[1]


def test_sync_changes_since_is_last_success_minus_one_day():
    store = InMemoryStore()
    store.record_run(run_row("success", "2026-11-10T03:00:00+00:00"))
    client = FakeClient()
    sync_changes(client, store)
    assert client.calls["fetch_changes"] == ["2026-11-09T03:00:00+00:00"]


def test_sync_changes_without_previous_run_fails_clearly():
    store = InMemoryStore()
    with pytest.raises(RuntimeError,
                       match="no successful run found: run backfill first"):
        sync_changes(FakeClient(), store)
    assert last_run(store)["status"] == "failed"


def test_failure_is_recorded_and_reraised():
    store = InMemoryStore()
    client = FakeClient(
        rounds={"Switzerland": [make_raw("r1")]},
        fail_at={("iter_rounds", 2): TechEuError("boom")})
    with pytest.raises(TechEuError):
        backfill(client, store, "2026-01-01", "2026-12-31")
    run = last_run(store)
    assert run["status"] == "failed"
    assert "boom" in run["error"]
    assert store.last_successful_run_started_at() is None


def _store_with_companies(n):
    store = InMemoryStore()
    backfill(FakeClient(rounds={"Switzerland": [
        make_raw(f"r{i}", f"co-{i}") for i in range(n)]}),
        store, "2026-01-01", "2026-12-31")
    return store


def test_fetch_company_details_fills_and_resumes():
    store = _store_with_companies(3)
    client = FakeClient(fail_at={("get_company", 2): BudgetExhaustedError("done")})
    run = fetch_company_details(client, store)
    assert run["status"] == "success"
    assert run["details_fetched"] == 1
    assert len(store.company_ids_missing_details(10)) == 2
    run = fetch_company_details(FakeClient(), store)
    assert run["details_fetched"] == 2
    assert store.company_ids_missing_details(10) == []


def test_fetch_company_details_counts_failures_and_continues():
    store = _store_with_companies(3)
    client = FakeClient(fail_at={("get_company", 2): TechEuError("nope")})
    run = fetch_company_details(client, store)
    assert run["status"] == "success"
    assert run["details_fetched"] == 2
    assert run["error"] == "details failed for 1 companies"
    assert len(store.company_ids_missing_details(10)) == 1


def test_reclean_reapplies_rules_without_client():
    store = InMemoryStore()
    raw = make_raw("r1")
    raw["stage"], raw["amountEur"] = "Seed", 1_000_000
    store.upsert_raw_rounds([raw])
    reclean(store)
    edited = store.all_rounds_with_company()[0]
    assert edited["size_category"] == "small"
    edited.pop("company")
    edited["size_category"] = "large"
    store.upsert_rounds([edited])
    run = reclean(store)
    assert store.all_rounds_with_company()[0]["size_category"] == "small"
    assert run["command"] == "reclean"
    assert run["requests_made"] == 0
