import pytest

from kaltstart.ingestion.store import InMemoryStore


def company(cid="c1", name="Acme"):
    return {
        "id": cid,
        "name": name,
        "country": "DE",
        "city_raw": "Berlin",
        "city": "Berlin",
        "region": "Berlin",
        "sectors": ["Fintech"],
        "techeu_url": f"https://tech.eu/companies/{cid}",
    }


def round_row(rid="a", company_id="c1", amount=1_000_000):
    return {
        "id": rid,
        "company_id": company_id,
        "date": "2026-01-15",
        "stage": "seed",
        "raw_round_type": "Seed",
        "amount_eur": amount,
        "amount_native": float(amount),
        "currency": "EUR",
        "size_category": "small",
        "investors": ["Fund A"],
        "source_url": "https://example.com/news",
        "source_domain": "example.com",
        "confidence": "high",
    }


def run(status, started_at):
    return {
        "command": "sync",
        "started_at": started_at,
        "finished_at": started_at,
        "status": status,
        "rounds_upserted": 0,
        "rounds_removed": 0,
        "companies_upserted": 0,
        "details_fetched": 0,
        "requests_made": 0,
        "error": None,
    }


def test_upserting_same_round_twice_keeps_one_row_with_latest_version():
    store = InMemoryStore()
    store.upsert_companies([company()])
    store.upsert_rounds([round_row(amount=1)])
    store.upsert_rounds([round_row(amount=2)])
    rows = store.all_rounds_with_company()
    assert len(rows) == 1
    assert rows[0]["amount_eur"] == 2
    assert store.counts()["rounds"] == 1


def test_upsert_raw_rounds_replaces_by_id():
    store = InMemoryStore()
    store.upsert_raw_rounds([{"id": "a", "v": 1}])
    store.upsert_raw_rounds([{"id": "a", "v": 2}])
    assert store.all_raw_rounds() == [{"id": "a", "v": 2}]


def test_upsert_companies_keeps_existing_details():
    store = InMemoryStore()
    store.upsert_companies([company()])
    store.set_company_details(
        "c1", {"website": "https://acme.io", "description": "d", "founded": 2020}
    )
    store.upsert_companies([company(name="Acme Renamed")])
    assert store.company_ids_missing_details(limit=10) == []
    store.upsert_rounds([round_row()])
    stored = store.all_rounds_with_company()[0]["company"]
    assert stored["name"] == "Acme Renamed"
    assert stored["website"] == "https://acme.io"
    assert stored["description"] == "d"
    assert stored["founded"] == 2020
    assert stored["details_fetched_at"] is not None


def test_company_ids_missing_details_limit_and_set_details():
    store = InMemoryStore()
    store.upsert_companies([company("c1"), company("c2"), company("c3")])
    assert len(store.company_ids_missing_details(limit=2)) == 2
    store.set_company_details(
        "c1", {"website": None, "description": None, "founded": None}
    )
    missing = store.company_ids_missing_details(limit=10)
    assert "c1" not in missing
    assert sorted(missing) == ["c2", "c3"]


def test_delete_rounds_returns_count_and_removes_raw():
    store = InMemoryStore()
    store.upsert_companies([company()])
    store.upsert_raw_rounds([{"id": "a"}, {"id": "b"}])
    store.upsert_rounds([round_row("a"), round_row("b")])
    assert store.delete_rounds(["a", "inconnu"]) == 1
    assert [r["id"] for r in store.all_rounds_with_company()] == ["b"]
    assert [r["id"] for r in store.all_raw_rounds()] == ["b"]
    assert store.counts() == {"raw_rounds": 1, "companies": 1, "rounds": 1}


def test_all_rounds_with_company_embeds_company_row():
    store = InMemoryStore()
    store.upsert_companies([company("c1"), company("c2", "Other")])
    store.upsert_rounds([round_row("a", "c1"), round_row("b", "c2")])
    rows = {r["id"]: r for r in store.all_rounds_with_company()}
    assert set(rows) == {"a", "b"}
    assert rows["a"]["company"]["id"] == "c1"
    assert rows["b"]["company"]["name"] == "Other"


def test_returned_rows_are_copies():
    store = InMemoryStore()
    store.upsert_companies([company()])
    store.upsert_rounds([round_row()])
    store.all_rounds_with_company()[0]["amount_eur"] = 999
    assert store.all_rounds_with_company()[0]["amount_eur"] == 1_000_000


def test_last_successful_run_started_at():
    store = InMemoryStore()
    assert store.last_successful_run_started_at() is None
    store.record_run(run("failed", "2026-03-01T00:00:00+00:00"))
    assert store.last_successful_run_started_at() is None
    store.record_run(run("success", "2026-01-01T00:00:00+00:00"))
    store.record_run(run("success", "2026-02-01T00:00:00+00:00"))
    store.record_run(run("failed", "2026-04-01T00:00:00+00:00"))
    assert store.last_successful_run_started_at() == "2026-02-01T00:00:00+00:00"


def test_supabase_store_from_env_requires_variables(monkeypatch):
    from kaltstart.ingestion.supabase_store import SupabaseStore

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL and SUPABASE_SERVICE_KEY"):
        SupabaseStore.from_env()
