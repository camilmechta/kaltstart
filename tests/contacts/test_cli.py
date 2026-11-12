import csv

from kaltstart.contacts.__main__ import main
from kaltstart.contacts.measurement import read_results
from kaltstart.contacts.models import FetchOutcome, Page

FILLER = "<p>" + "We build robots for warehouses. " * 10 + "</p>"


class FakeFetcher:
    def __init__(self, sites):
        self.sites = sites

    def fetch_site(self, website):
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
    assert "Founder name (reported): 1/2 (50%)" in printed
    assert str(out) in printed
    # The verifier is told what each check value means.
    for word in ("email_check", "founder_check", "confirmed", "wrong", "missed", "none_exists"):
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
    rows[0]["email_check"], rows[0]["founder_check"] = "confirmed", "none_exists"
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
