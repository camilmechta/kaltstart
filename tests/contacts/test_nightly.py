from datetime import datetime, timedelta, timezone

import pytest

from kaltstart.contacts.exclusions import person_key
from kaltstart.contacts.models import FetchOutcome, Page
from kaltstart.contacts.nightly import (
    DEFAULT_MAX, MAX_UNREACHABLE, MAX_WRITE_ERRORS, RECENT_ROUND_DAYS, REREAD_DAYS,
    RETRY_DAYS, due_companies, next_state, run)
from kaltstart.contacts.store import InMemoryContactStore

NOW = datetime(2026, 11, 15, 3, 17, tzinfo=timezone.utc)
FILLER = "<p>" + "We build robots for warehouses. " * 10 + "</p>"
UNREACHABLE = "unreachable"


def site(host, team="", home=""):
    def page(path, kind, body):
        return Page(f"https://{host}{path}", kind, f"<html><body>{FILLER}{body}</body></html>")
    return FetchOutcome("ok", (page("/", "home", home), page("/team", "team", team)), (host,))


class FakeFetcher:
    """Maps a website to a FetchOutcome, or to UNREACHABLE."""

    def __init__(self, sites):
        self.sites = sites
        self.visited = []

    def fetch_site(self, website):
        self.visited.append(website)
        outcome = self.sites[website]
        if outcome == UNREACHABLE:
            host = website.split("//")[1]
            return FetchOutcome("unreachable", (), (host,))
        return outcome


ANNA = "<p>Anna Muster, Founder</p>"
BEN = "<p>Ben Probe, CTO</p>"


def two_companies():
    store = InMemoryContactStore()
    store.add_company("c1", "Example Robotics", "https://example.ch",
                      created_at="2026-01-01T00:00:00+00:00")
    store.add_company("c2", "Example Foods", "https://example.com",
                      created_at="2026-02-01T00:00:00+00:00")
    store.rounds += [{"company_id": "c1", "date": "2026-06-01"},
                     {"company_id": "c2", "date": "2026-06-01"}]
    fetcher = FakeFetcher({
        "https://example.ch": site("example.ch", team=ANNA + BEN + "<p>info@example.ch</p>"),
        "https://example.com": site("example.com", team="<p>Nothing here</p>"),
    })
    return store, fetcher


def test_constants_match_the_spec():
    assert (REREAD_DAYS, RETRY_DAYS, MAX_UNREACHABLE, RECENT_ROUND_DAYS, DEFAULT_MAX,
            MAX_WRITE_ERRORS) == (30, 7, 3, 365, 300, 5)


@pytest.mark.parametrize("outcome", ["ok", "no_address", "contact_form_only",
                                     "other_domain_only", "little_text", "not_own_site",
                                     "robots_forbidden"])
def test_a_site_that_was_read_is_due_in_30_days(outcome):
    assert next_state(outcome, 2, NOW) == (0, NOW + timedelta(days=30), "replace")


def test_unreachable_is_retried_after_7_days_and_keeps_rows():
    assert next_state("unreachable", 0, NOW) == (1, NOW + timedelta(days=7), "keep")
    assert next_state("unreachable", 1, NOW) == (2, NOW + timedelta(days=7), "keep")


def test_third_unreachable_deletes_rows_and_waits_30_days():
    assert next_state("unreachable", 2, NOW) == (0, NOW + timedelta(days=30), "delete")


def candidate(id, created="2026-01-01T00:00:00+00:00", checked=None, next_at=None):
    return {"id": id, "name": id, "website": f"https://{id}.example.ch", "created_at": created,
            "contacts_checked_at": checked, "contacts_outcome": None,
            "contacts_attempts": 0, "contacts_next_at": next_at}


def test_due_companies_order_and_cap():
    past = (NOW - timedelta(days=1)).isoformat()
    older = (NOW - timedelta(days=5)).isoformat()
    future = (NOW + timedelta(days=1)).isoformat()
    candidates = [
        candidate("overdue", checked=past, next_at=past),
        candidate("new-b", created="2026-03-01T00:00:00+00:00"),
        candidate("not-due", checked=past, next_at=future),
        candidate("long-overdue", checked=older, next_at=older),
        candidate("new-a", created="2026-02-01T00:00:00+00:00"),
        candidate("no-recent-round"),
        candidate("excluded"),
    ]
    recent = {c["id"] for c in candidates} - {"no-recent-round"}
    picked = due_companies(candidates, recent, {"excluded"}, NOW, limit=10)
    assert [c["id"] for c in picked] == ["new-a", "new-b", "long-overdue", "overdue"]
    assert [c["id"] for c in due_companies(candidates, recent, {"excluded"}, NOW, limit=3)] \
        == ["new-a", "new-b", "long-overdue"]


def test_first_run_stores_rows_state_and_summary():
    store, fetcher = two_companies()
    summary = run(store, fetcher, now=NOW)
    assert fetcher.visited == ["https://example.ch", "https://example.com"]
    assert [(e["company_id"], e["address"], e["type"], e["source_url"], e["read_at"])
            for e in store.emails] == [
        ("c1", "info@example.ch", "generic", "https://example.ch/team", NOW.isoformat())]
    assert [(p["company_id"], p["name"], p["title"], p["categories"], p["level"])
            for p in store.people] == [
        ("c1", "Anna Muster", "Founder", ["leadership"], "head"),
        ("c1", "Ben Probe", "CTO", ["leadership"], "head")]
    c1, c2 = store.companies["c1"], store.companies["c2"]
    assert (c1["contacts_outcome"], c1["contacts_checked_at"], c1["contacts_next_at"]) == (
        "ok", NOW.isoformat(), (NOW + timedelta(days=30)).isoformat())
    assert c2["contacts_outcome"] == "no_address"
    assert (summary["status"], summary["country"], summary["companies_visited"],
            summary["with_address"], summary["with_people"], summary["error"]) == (
        "success", "Switzerland", 2, 1, 1, None)
    assert summary["outcomes"] == {"ok": 1, "no_address": 1}
    assert summary["started_at"] == NOW.isoformat()
    assert store.runs == [summary]


def test_a_person_who_left_the_site_is_removed_at_the_next_reading():
    store, fetcher = two_companies()
    run(store, fetcher, now=NOW)
    fetcher.sites["https://example.ch"] = site("example.ch", team=BEN + "<p>info@example.ch</p>")
    run(store, fetcher, now=NOW + timedelta(days=31))
    assert [p["name"] for p in store.people] == ["Ben Probe"]


def test_people_without_an_address_are_stored():
    store, fetcher = two_companies()
    fetcher.sites["https://example.ch"] = site("example.ch", team=ANNA)
    run(store, fetcher, now=NOW)
    assert [p["name"] for p in store.people] == ["Anna Muster"]
    c1 = store.companies["c1"]
    assert (c1["contacts_outcome"], c1["contacts_next_at"]) == (
        "no_address", (NOW + timedelta(days=30)).isoformat())


def test_rows_survive_two_unreachable_runs_and_go_at_the_third():
    store, fetcher = two_companies()
    run(store, fetcher, now=NOW)
    fetcher.sites["https://example.ch"] = UNREACHABLE
    when = NOW + timedelta(days=31)
    run(store, fetcher, now=when)
    run(store, fetcher, now=when + timedelta(days=8))
    assert {e["company_id"] for e in store.emails} == {"c1"}
    assert store.companies["c1"]["contacts_attempts"] == 2
    run(store, fetcher, now=when + timedelta(days=16))
    assert store.emails == [] and store.people == []
    assert store.companies["c1"]["contacts_attempts"] == 0
    assert store.companies["c1"]["contacts_outcome"] == "unreachable"


def test_an_excluded_company_is_never_visited_and_its_rows_go():
    store, fetcher = two_companies()
    run(store, fetcher, now=NOW)
    store.excluded.append({"company_id": "c1", "person_key": None})
    fetcher.visited.clear()
    run(store, fetcher, now=NOW + timedelta(days=31))
    assert fetcher.visited == ["https://example.com"]
    assert store.emails == [] and store.people == []


def test_an_excluded_person_is_not_stored():
    store, fetcher = two_companies()
    store.excluded.append({"company_id": "c1", "person_key": person_key("c1", "anna muster")})
    run(store, fetcher, now=NOW)
    assert [p["name"] for p in store.people] == ["Ben Probe"]


def test_rows_of_a_company_without_a_recent_round_are_deleted():
    store, fetcher = two_companies()
    run(store, fetcher, now=NOW)
    store.rounds[0]["date"] = (NOW - timedelta(days=400)).date().isoformat()
    fetcher.visited.clear()
    run(store, fetcher, now=NOW + timedelta(days=1))
    assert store.emails == [] and store.people == []
    assert fetcher.visited == []


def test_a_second_run_at_the_same_time_visits_nothing():
    store, fetcher = two_companies()
    run(store, fetcher, now=NOW)
    fetcher.visited.clear()
    summary = run(store, fetcher, now=NOW)
    assert fetcher.visited == [] and summary["companies_visited"] == 0


def test_the_cap_limits_a_run_and_the_next_one_continues():
    store, fetcher = two_companies()
    run(store, fetcher, limit=1, now=NOW)
    assert fetcher.visited == ["https://example.ch"]
    run(store, fetcher, limit=1, now=NOW)
    assert fetcher.visited == ["https://example.ch", "https://example.com"]


class FailingStore(InMemoryContactStore):
    def __init__(self, failing_ids):
        super().__init__()
        self.failing_ids = failing_ids

    def replace_contacts(self, company_id, emails, people):
        if company_id in self.failing_ids:
            raise OSError("write refused for anna.muster@example.ch")
        super().replace_contacts(company_id, emails, people)


def many_companies(store, count):
    sites = {}
    for n in range(count):
        store.add_company(f"c{n}", f"Example {n}", f"https://c{n}.example.ch",
                          created_at=f"2026-01-{n + 1:02d}T00:00:00+00:00")
        store.rounds.append({"company_id": f"c{n}", "date": "2026-06-01"})
        sites[f"https://c{n}.example.ch"] = site(f"c{n}.example.ch",
                                                 team=f"<p>info@c{n}.example.ch</p>")
    return FakeFetcher(sites)


def test_one_failed_write_leaves_that_company_due_and_the_run_goes_on():
    store = FailingStore({"c1"})
    fetcher = many_companies(store, 3)
    summary = run(store, fetcher, now=NOW)
    assert {e["company_id"] for e in store.emails} == {"c0", "c2"}
    assert store.companies["c1"]["contacts_checked_at"] is None
    assert (summary["status"], summary["companies_visited"]) == ("success", 2)


def test_five_failed_writes_in_a_row_stop_the_run():
    store = FailingStore({f"c{n}" for n in range(1, 7)})
    fetcher = many_companies(store, 8)
    summary = run(store, fetcher, now=NOW)
    assert len(fetcher.visited) == 6                # c0, then c1 to c5
    assert (summary["status"], summary["error"]) == ("failed", "OSError")
    assert store.runs == [summary]


def test_unreadable_exclusions_stop_the_run_before_any_visit():
    store, fetcher = two_companies()
    store.exclusions = lambda: (_ for _ in ()).throw(RuntimeError("anna.muster@example.ch"))
    summary = run(store, fetcher, now=NOW)
    assert fetcher.visited == []
    assert (summary["status"], summary["error"]) == ("failed", "RuntimeError")
    assert store.runs == [summary]


def test_the_run_summary_holds_no_name_address_or_page():
    store, fetcher = two_companies()
    text = repr(run(store, fetcher, now=NOW))
    for secret in ("Anna", "Muster", "Probe", "@", "example.ch", "Example Robotics"):
        assert secret not in text
