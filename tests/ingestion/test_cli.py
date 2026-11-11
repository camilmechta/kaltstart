import copy
import json
from datetime import date
from pathlib import Path

import pytest

from kaltstart.ingestion import __main__ as cli
from kaltstart.ingestion.__main__ import main, months_back
from kaltstart.ingestion.store import InMemoryStore
from kaltstart.ingestion.techeu_client import TechEuError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "techeu"
TEMPLATE = json.loads((FIXTURES / "rounds_page1.json").read_text())["data"][0]
COMPANY_PAYLOAD = json.loads((FIXTURES / "company.json").read_text())


def make_raw(round_id, company_id="co-1", country="Switzerland", city="Lausanne"):
    raw = copy.deepcopy(TEMPLATE)
    raw["id"] = round_id
    raw["company"].update(id=company_id, country=country, city=city,
                          name=f"Company {company_id}")
    return raw


class FakeClient:
    def __init__(self, rounds=None, error=None):
        self.rounds = rounds or {}
        self.error = error
        self.requests_made = 0
        self.date_ranges = []

    def iter_rounds(self, country, date_from, date_to):
        self.requests_made += 1
        self.date_ranges.append((date_from, date_to))
        if self.error:
            raise self.error
        yield from self.rounds.get(country, [])

    def fetch_changes(self, since):
        self.requests_made += 1
        return [], []

    def get_company(self, company_id):
        self.requests_made += 1
        return COMPANY_PAYLOAD


def company(cid, country="Switzerland", city="Zurich", city_raw=None):
    return {"id": cid, "name": cid, "country": country, "city": city,
            "city_raw": city_raw if city_raw is not None else city,
            "region": None, "sectors": [], "techeu_url": f"https://funding.tech.eu/companies/{cid}"}


def round_row(rid, cid, stage, size_category, amount_eur):
    return {"id": rid, "company_id": cid, "date": "2026-01-01", "stage": stage,
            "raw_round_type": None, "amount_eur": amount_eur,
            "amount_native": amount_eur, "currency": "EUR",
            "size_category": size_category, "investors": [],
            "source_url": f"https://funding.tech.eu/deals/{rid}",
            "source_domain": None, "confidence": "high"}


def report_store():
    store = InMemoryStore()
    store.upsert_companies([
        company("c1"), company("c2", city="Zurich"),
        company("c3", country="Germany", city="Berlin", city_raw="berlin "),
        company("c4", country="Austria", city=None, city_raw="Vienna region")])
    store.upsert_rounds([
        round_row("r1", "c1", "Seed", "small", 1_000_000),
        round_row("r2", "c2", "Seed", "small", 3_000_000),
        round_row("r3", "c3", "Series A", "medium", 10_000_000),
        round_row("r4", "c4", "Other", "large", None),
        round_row("r5", "c1", "Pre-Seed", "small", None)])
    return store


def test_backfill_runs_and_stores_rounds(capsys):
    store = InMemoryStore()
    client = FakeClient(rounds={"Switzerland": [make_raw("r1"), make_raw("r2", "co-2")]})
    assert main(["backfill", "--months", "12"], client=client, store=store) == 0
    assert store.counts()["rounds"] == 2
    out = capsys.readouterr().out
    assert "rounds_upserted" in out
    assert "details_fetched: 2" in out
    assert "command: details" in out


def test_backfill_date_range_uses_months(monkeypatch):
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 5, 31))
    client = FakeClient()
    assert main(["backfill", "--months", "3"], client=client, store=InMemoryStore()) == 0
    assert client.date_ranges[0] == ("2026-02-28", "2026-05-31")


def test_sync_without_previous_run_fails(capsys):
    assert main(["sync"], client=FakeClient(), store=InMemoryStore()) == 1
    captured = capsys.readouterr()
    assert "run backfill first" in captured.err
    assert "Traceback" not in captured.err


def test_sync_after_backfill_succeeds(capsys):
    store = InMemoryStore()
    client = FakeClient(rounds={"Switzerland": [make_raw("r1")]})
    assert main(["backfill"], client=client, store=store) == 0
    capsys.readouterr()
    assert main(["sync"], client=client, store=store) == 0
    assert "command: sync" in capsys.readouterr().out


def test_techeu_error_returns_1(capsys):
    client = FakeClient(error=TechEuError("boom"))
    assert main(["backfill"], client=client, store=InMemoryStore()) == 1
    assert "error: boom" in capsys.readouterr().err


def test_reclean_runs(capsys):
    store = InMemoryStore()
    store.upsert_raw_rounds([make_raw("r1")])
    assert main(["reclean"], store=store) == 0
    assert store.counts()["rounds"] == 1
    assert "command: reclean" in capsys.readouterr().out


def test_report_prints_counts_sizes_and_medians(capsys):
    assert main(["report"], store=report_store()) == 0
    out = capsys.readouterr().out
    for line in ("raw_rounds: 0", "companies: 4", "rounds: 5"):
        assert line in out
    for size in ("small", "medium", "large"):
        assert any(l.split()[:1] == [size] for l in out.splitlines()), size
    assert "Switzerland" in out and "Germany" in out
    seed = next(l for l in out.splitlines() if l.startswith("Seed") and "2,000,000" in l)
    assert seed
    series_a = next(l for l in out.splitlines() if l.startswith("Series A"))
    assert "10,000,000" in series_a
    # "Other" is not a known stage; Pre-Seed has no amounts: no median, no crash.
    medians = out.split("Median amount_eur by stage")[1]
    assert "Other" not in medians
    assert "Pre-Seed" in medians


def test_report_on_empty_store(capsys):
    assert main(["report"], store=InMemoryStore()) == 0
    assert "rounds: 0" in capsys.readouterr().out


def test_cities_prints_city_with_country_and_count(capsys):
    store = InMemoryStore()
    client = FakeClient(rounds={"Switzerland": [
        make_raw("r1", "co-1", city="Zurich"), make_raw("r2", "co-2", city="Zurich")]})
    main(["backfill"], client=client, store=store)
    capsys.readouterr()
    assert main(["cities"], store=store) == 0
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if "Zurich" in l)
    assert "Switzerland" in line and "2" in line


def test_cities_sorting_none_label_and_raw_differences(capsys):
    assert main(["cities"], store=report_store()) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert any("(none)" in l and "Austria" in l for l in lines)
    order = [next(i for i, l in enumerate(lines) if name in l)
             for name in ("Austria", "Germany", "Switzerland")]
    assert order == sorted(order)
    assert "berlin " in out or "'berlin '" in out
    assert "Vienna region" in out


def test_cities_on_empty_store():
    assert main(["cities"], store=InMemoryStore()) == 0


@pytest.mark.parametrize("argv", [[], ["nonsense"], ["backfill", "--bogus"]])
def test_usage_errors_return_2(argv):
    assert main(argv) == 2


def test_nothing_is_built_before_arguments_are_parsed(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("constructed too early")
    monkeypatch.setattr(cli, "_default_client", boom)
    monkeypatch.setattr(cli, "_default_store", boom)
    assert main([]) == 2


def test_report_cities_reclean_never_build_a_client(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("client constructed")
    monkeypatch.setattr(cli, "_default_client", boom)
    store = InMemoryStore()
    for command in ("report", "cities", "reclean"):
        assert main([command], store=store) == 0


class FalsyStore(InMemoryStore):
    def __bool__(self):
        return False


def test_a_falsy_store_is_still_used(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("default store constructed")
    monkeypatch.setattr(cli, "_default_store", boom)
    assert main(["report"], store=FalsyStore()) == 0
    assert main(["reclean"], store=FalsyStore()) == 0


def test_missing_supabase_env_returns_1(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    assert main(["sync"]) == 1
    assert "SUPABASE_URL" in capsys.readouterr().err


@pytest.mark.parametrize("today,months,expected", [
    (date(2026, 11, 11), 12, date(2025, 11, 11)),
    (date(2026, 3, 31), 1, date(2026, 2, 28)),
    (date(2024, 3, 31), 1, date(2024, 2, 29)),
    (date(2026, 1, 15), 2, date(2025, 11, 15)),
    (date(2026, 5, 31), 3, date(2026, 2, 28)),
])
def test_months_back(today, months, expected):
    assert months_back(today, months) == expected
