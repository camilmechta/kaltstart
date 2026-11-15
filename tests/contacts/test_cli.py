import csv

from kaltstart.contacts.__main__ import main
from kaltstart.contacts.measurement import read_results
from kaltstart.contacts.models import FetchOutcome, Page

FILLER = "<p>" + "We build robots for warehouses. " * 10 + "</p>"


class FakeFetcher:
    def __init__(self, sites):
        self.sites = sites
        self.visited = []

    def fetch_site(self, website):
        self.visited.append(website)
        outcome = self.sites[website]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def site(host, body):
    page = Page(f"https://{host}/", "team", f"<html><body>{FILLER}{body}</body></html>")
    return FetchOutcome("ok", (page,), (host,))


def write_sample(path, websites):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["company_id", "name", "website", "size_category"])
        for i, website in enumerate(websites):
            writer.writerow([f"c{i}", f"Company {i}", website, "small"])


def test_measure_writes_results_and_prints_reported_rates(tmp_path, capsys):
    sample, out = tmp_path / "sample.csv", tmp_path / "local" / "results.csv"
    write_sample(sample, ["https://example.ch", "https://example.de"])
    fetcher = FakeFetcher({
        "https://example.ch": site("example.ch", "<p>Anna Muster, Founder</p><p>anna@example.ch</p>"),
        "https://example.de": site("example.de", "<p>Nothing</p>"),
    })
    assert main(["measure", str(sample), "--out", str(out)], fetcher=fetcher) == 0
    rows = read_results(out)
    assert [r["company_id"] for r in rows] == ["c0", "c1"]
    assert rows[0]["contact_address"] == "anna@example.ch"
    assert rows[1]["failure"] == "no_address"
    printed = capsys.readouterr().out
    assert "1/2 example.ch: ok" in printed
    assert "2/2 example.de: no_address" in printed
    assert "Usable contact (reported): 1/2 (50%)" in printed
    assert "People (reported): 1/2 (50%)" in printed
    assert str(out) in printed
    # The verifier is told what each check value means.
    for word in ("email_check", "people_check", "confirmed", "wrong", "missed", "none_exists"):
        assert word in printed
    assert "every reported" in printed


def test_measure_continues_after_a_failing_company(tmp_path):
    sample, out = tmp_path / "sample.csv", tmp_path / "results.csv"
    write_sample(sample, ["https://example.ch", "https://example.de"])
    fetcher = FakeFetcher({
        "https://example.ch": RuntimeError("boom"),
        "https://example.de": site("example.de", "<p>info@example.de</p>"),
    })
    assert main(["measure", str(sample), "--out", str(out)], fetcher=fetcher) == 0
    rows = read_results(out)
    assert rows[0]["failure"] == "unreachable"
    assert rows[1]["emails"].startswith("info@example.de|generic|")


def measured(tmp_path):
    sample, out = tmp_path / "sample.csv", tmp_path / "results.csv"
    write_sample(sample, ["https://example.ch"])
    fetcher = FakeFetcher({"https://example.ch": site("example.ch", "<p>info@example.ch</p>")})
    main(["measure", str(sample), "--out", str(out)], fetcher=fetcher)
    return out


def test_summary_refuses_unverified_results(tmp_path, capsys):
    out = measured(tmp_path)
    capsys.readouterr()
    assert main(["summary", str(out), "--out", str(tmp_path / "summary.md")]) == 1
    assert "c0" in capsys.readouterr().err
    assert not (tmp_path / "summary.md").exists()


def test_summary_writes_file(tmp_path):
    out = measured(tmp_path)
    rows = read_results(out)
    rows[0]["email_check"], rows[0]["people_check"] = "confirmed", "none_exists"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    target = tmp_path / "docs" / "summary.md"
    assert main(["summary", str(out), "--out", str(target)]) == 0
    assert target.read_text(encoding="utf-8").startswith("# Phase 2 measurement")


def test_no_command_returns_2():
    assert main([]) == 2


def test_missing_sample_file_returns_1(tmp_path, capsys):
    assert main(["measure", str(tmp_path / "nope.csv")]) == 1
    assert "nope.csv" in capsys.readouterr().err


def test_summary_refuses_an_old_results_file(tmp_path, capsys):
    old = tmp_path / "old.csv"
    old.write_text("company_id,emails,founders,email_check,founder_check\n"
                   "c1,,,none_exists,none_exists\n", encoding="utf-8")
    assert main(["summary", str(old), "--out", str(tmp_path / "summary.md")]) == 1
    assert "people" in capsys.readouterr().err


# --- run and status: the nightly commands -------------------------------------

def contact_store():
    from kaltstart.contacts.store import InMemoryContactStore
    store = InMemoryContactStore()
    store.add_company("c1", "Example Robotics", "https://example.ch",
                      created_at="2026-01-01T00:00:00+00:00")
    store.add_company("c2", "Example Foods", "https://example.de",
                      created_at="2026-02-01T00:00:00+00:00")
    store.rounds += [{"company_id": "c1", "date": "2099-01-01"},
                     {"company_id": "c2", "date": "2099-01-01"}]
    return store


def contact_fetcher():
    return FakeFetcher({
        "https://example.ch": site("example.ch",
                                   "<p>Anna Muster, Founder</p><p>anna@example.ch</p>"),
        "https://example.de": site("example.de", "<p>Nothing</p>"),
    })


def test_run_prints_counts_only(capsys):
    store = contact_store()
    assert main(["run"], fetcher=contact_fetcher(), store=store) == 0
    printed = capsys.readouterr().out
    assert "Visited 2, with an address 1, with people 1" in printed
    assert "ok: 1" in printed and "no_address: 1" in printed
    for secret in ("Anna", "Muster", "@", "example.ch", "Example Robotics"):
        assert secret not in printed
    assert store.runs[0]["companies_visited"] == 2


def test_run_max_limits_the_companies_visited():
    store, fetcher = contact_store(), contact_fetcher()
    assert main(["run", "--max", "1"], fetcher=fetcher, store=store) == 0
    assert fetcher.visited == ["https://example.ch"]


def test_run_reads_only_the_country_asked_for():
    store, fetcher = contact_store(), contact_fetcher()
    assert main(["run", "--country", "Germany"], fetcher=fetcher, store=store) == 0
    assert fetcher.visited == []


def test_a_failed_run_returns_1(capsys):
    store = contact_store()
    store.exclusions = lambda: (_ for _ in ()).throw(RuntimeError("anna@example.ch"))
    assert main(["run"], fetcher=contact_fetcher(), store=store) == 1
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err
    assert "@" not in captured.out + captured.err


def test_status_prints_counts_only(capsys):
    store = contact_store()
    main(["run", "--max", "1"], fetcher=contact_fetcher(), store=store)
    capsys.readouterr()
    assert main(["status"], store=store) == 0
    printed = capsys.readouterr().out
    for line in ("Eligible: 2", "Visited: 1", "With an address: 1", "With people: 1",
                 "Due now: 1", "ok: 1"):
        assert line in printed, line
    for secret in ("Anna", "Muster", "@", "example.ch", "Example Robotics"):
        assert secret not in printed


def test_a_database_error_in_status_prints_its_kind_only(capsys):
    store = contact_store()
    store.candidate_companies = lambda country: (_ for _ in ()).throw(
        ValueError("row anna@example.ch refused"))
    assert main(["status"], store=store) == 1
    captured = capsys.readouterr()
    assert "ValueError" in captured.err
    assert "@" not in captured.out + captured.err
