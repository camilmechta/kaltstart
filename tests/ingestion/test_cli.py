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


def test_report_prints_share_of_companies_with_a_website(capsys):
    store = report_store()
    ids = sorted({i["company"]["id"] for i in store.all_rounds_with_company()})
    store.set_company_details(
        ids[0], {"website": "https://example.ch", "description": None, "founded": None})
    store.set_company_details(
        ids[1], {"website": None, "description": None, "founded": None})
    assert main(["report"], store=store) == 0
    out = capsys.readouterr().out
    assert "companies_with_details: 2 of 4 (50%)" in out
    assert "companies_with_website: 1 of 4 (25%)" in out


def sample_store():
    store = InMemoryStore()
    companies, rounds = [], []
    for i in range(35):
        companies.append(company(f"ch-{i:02d}"))
        rounds.append(round_row(f"r-ch-{i:02d}", f"ch-{i:02d}", "Seed", "small", 1_000_000))
    for i in range(10):
        companies.append(company(f"de-{i:02d}", country="Germany", city="Berlin"))
        rounds.append(round_row(f"r-de-{i:02d}", f"de-{i:02d}", "Seed", "small", 1_000_000))
    store.upsert_companies(companies)
    store.upsert_rounds(rounds)
    for c in companies:
        number = int(c["id"].split("-")[1])
        has_site = not (c["id"].startswith("ch-") and number >= 30)   # 5 Swiss without a site
        store.set_company_details(c["id"], {
            "website": f"https://{c['id']}.example.ch" if has_site else None,
            "description": None, "founded": None})
    return store


def sample_rows(capsys, *argv, store=None):
    assert main(["sample", *argv], store=store or sample_store()) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "company_id,name,website,size_category"
    return [line.split(",") for line in lines[1:]]


def test_sample_prints_20_swiss_companies_with_a_website(capsys):
    rows = sample_rows(capsys)
    assert len(rows) == 20
    assert len({r[0] for r in rows}) == 20
    assert all(r[0].startswith("ch-") and int(r[0][3:]) < 30 for r in rows)
    assert all(r[2].startswith("https://") for r in rows)


def test_sample_is_reproducible(capsys):
    first = sample_rows(capsys)
    assert sample_rows(capsys) == first
    assert sample_rows(capsys, "--seed", "2027") != first


def test_sample_does_not_depend_on_row_order(capsys):
    store = sample_store()
    reordered = InMemoryStore()
    items = store.all_rounds_with_company()
    reordered.upsert_companies([{k: v for k, v in i["company"].items()
                                 if k in company("x")} for i in reversed(items)])
    reordered.upsert_rounds([{k: v for k, v in i.items() if k != "company"}
                             for i in reversed(items)])
    for i in items:
        reordered.set_company_details(i["company"]["id"], {
            "website": i["company"]["website"], "description": None, "founded": None})
    assert sample_rows(capsys, store=reordered) == sample_rows(capsys, store=store)


def test_sample_size_category_is_that_of_the_latest_round(capsys):
    store = sample_store()
    later = round_row("r-late", "ch-00", "Series B", "large", 30_000_000)
    later["date"] = "2026-06-01"
    store.upsert_rounds([later])
    rows = sample_rows(capsys, "--n", "30", store=store)
    assert next(r for r in rows if r[0] == "ch-00")[3] == "large"
    assert next(r for r in rows if r[0] == "ch-01")[3] == "small"


def test_sample_exclude_seed(capsys):
    first = {r[0] for r in sample_rows(capsys, "--n", "10")}
    second = {r[0] for r in sample_rows(capsys, "--n", "10", "--seed", "2027",
                                        "--exclude-seed", "2026")}
    assert len(second) == 10
    assert not first & second


def test_sample_with_fewer_companies_than_n_prints_them_all(capsys):
    assert len(sample_rows(capsys, "--n", "50")) == 30


def test_sample_other_country(capsys):
    rows = sample_rows(capsys, "--country", "Germany")
    assert len(rows) == 10 and all(r[0].startswith("de-") for r in rows)


def test_sample_never_builds_a_client(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("client constructed")
    monkeypatch.setattr(cli, "_default_client", boom)
    assert main(["sample"], store=sample_store()) == 0
