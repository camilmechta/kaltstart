import threading
from datetime import date, datetime, timedelta, timezone

import pytest

from kaltstart.api.rules import Refusal
from kaltstart.api.store import (
    CompanyRow, EmailRow, InMemoryAppStore, ListFilters, NewMail, PersonRow, Profile, Showcase)

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def company(n, country="Switzerland", sector="Robotics", size="small", days=10, **changes):
    values = dict(id=f"c{n}", name=f"Example {n}", country=country, city="Zurich",
                  sector=sector, size_category=size, round_id=f"r{n}",
                  round_date=(NOW - timedelta(days=days)).date(), stage="Seed",
                  amount_eur=2_000_000, amount_native=None, currency=None,
                  investors=("Example Ventures",), description="Robots.",
                  website=f"https://c{n}.example.ch", source_url="https://example.com/round")
    values.update(changes)
    return CompanyRow(**values)


def new_mail(company_id="c1", person_key=None):
    return NewMail(company_id=company_id, round_id="r1", address="info@c1.example.ch",
                   address_type="generic", person_name=None, person_key=person_key,
                   person_choice="team", person_source_url=None, style="direct",
                   language="en", company_line=None, used_company_line=False,
                   subject="Example internship?", body="Hi Example team!")


def store_with(*companies, with_address=True):
    store = InMemoryAppStore(invitation="code-123")
    for c in companies:
        store.add_company(c, emails=[EmailRow(f"info@{c.id}.example.ch", "generic",
                                              f"https://{c.id}.example.ch/")] if with_address else [],
                          people=[])
    return store


def ids(store, filters=ListFilters(), student="s1"):
    rows, _total = store.companies(filters, student, NOW)
    return [r.id for r in rows]


def test_eligible_companies_are_sorted_by_newest_round():
    store = store_with(company(1, days=40), company(2, days=5), company(3, days=400))
    assert ids(store) == ["c2", "c1"]


def test_a_company_without_an_address_is_hidden():
    store = store_with(company(1))
    store.add_company(company(2), emails=[], people=[])
    assert ids(store) == ["c1"]


def test_an_excluded_company_is_hidden_and_has_no_page():
    store = store_with(company(1), company(2))
    store.exclude_company("c2")
    assert ids(store) == ["c1"]
    assert store.company("c2") is None and store.company("c1") is not None


def test_a_full_company_is_hidden_except_for_a_student_who_wrote_to_it():
    store = store_with(company(1))
    for student in ("a", "b", "s1"):
        assert isinstance(store.reserve(student, new_mail(), NOW), str)
    assert ids(store, student="other") == []
    assert ids(store, student="s1") == ["c1"]


@pytest.mark.parametrize("filters,expected", [
    (ListFilters(query="example 2"), ["c2"]),
    (ListFilters(countries=("Germany",)), ["c2"]),
    (ListFilters(sectors=("Fintech",)), ["c3"]),
    (ListFilters(sizes=("large",)), ["c3"]),
    (ListFilters(months=3), ["c1", "c2"]),
])
def test_filters(filters, expected):
    store = store_with(company(1, days=10), company(2, country="Germany", days=20),
                       company(3, sector="Fintech", size="large", days=200))
    assert ids(store, filters) == expected


def test_paging_by_fifty():
    store = store_with(*[company(n, days=n % 300) for n in range(51)])
    first, total = store.companies(ListFilters(), "s1", NOW)
    second, _ = store.companies(ListFilters(page=2), "s1", NOW)
    assert (len(first), len(second), total) == (50, 1, 51)


def test_reserve_applies_the_rules():
    store = store_with(company(1))
    assert isinstance(store.reserve("s1", new_mail(), NOW), str)
    assert store.reserve("s1", new_mail(), NOW) == Refusal("company_done", None)


def test_only_one_of_ten_concurrent_keeps_gets_the_last_slot():
    store = store_with(company(1))
    store.reserve("a", new_mail(), NOW)
    store.reserve("b", new_mail(), NOW)
    results = []
    threads = [threading.Thread(target=lambda n=n: results.append(store.reserve(f"t{n}", new_mail(), NOW)))
               for n in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(isinstance(r, str) for r in results) == 1


def test_status_changes_only_on_the_students_own_mail():
    store = store_with(company(1))
    mail_id = store.reserve("s1", new_mail(), NOW)
    assert not store.set_status("other", mail_id, "sent", NOW)
    assert store.set_status("s1", mail_id, "sent", NOW)
    assert store.mail("s1", mail_id).status == "sent"
    assert store.mail("other", mail_id) is None


def test_profiles_and_showcases_belong_to_one_student():
    store = InMemoryAppStore(invitation="x")
    store.save_profile(Profile(id="s1", first_name="Lea"), [Showcase(1, "I built a thing.", None)])
    assert store.profile("s1").first_name == "Lea" and store.profile("s2") is None
    assert store.showcases("s2") == []


def test_deleting_a_student_anonymises_their_mails():
    store = store_with(company(1))
    store.save_profile(Profile(id="s1", first_name="Lea"), [Showcase(1, "I built a thing.", None)])
    mail_id = store.reserve("s1", new_mail(), NOW)
    store.delete_student("s1")
    assert store.profile("s1") is None and store.showcases("s1") == []
    kept = store.all_mails()[0]
    assert kept.id == mail_id and kept.student_id is None
    assert (kept.subject, kept.body, kept.person_name, kept.address, kept.company_line) == (
        None, None, None, None, None)
    assert kept.company_id == "c1" and kept.status == "generated"
    assert ids(store, student="z") == ["c1"]


def test_people_and_emails_of_a_company():
    store = InMemoryAppStore(invitation="x")
    person = PersonRow("Anna Muster", "Head of Growth", ("growth",), "head",
                       "https://c1.example.ch/team", date(2026, 11, 15))
    store.add_company(company(1), emails=[EmailRow("jobs@c1.example.ch", "careers", "https://c1.example.ch/jobs")],
                      people=[person])
    assert store.people("c1") == [person]
    assert store.emails("c1")[0].address == "jobs@c1.example.ch"


def test_filter_on_companies_with_a_person():
    store = InMemoryAppStore(invitation="x")
    person = PersonRow("Anna Muster", "CEO", ("leadership",), "head", "https://c1.example.ch/team",
                       date(2026, 11, 15))
    store.add_company(company(1), emails=[EmailRow("info@c1.example.ch", "generic", "u")], people=[person])
    store.add_company(company(2), emails=[EmailRow("info@c2.example.ch", "generic", "u")], people=[])
    assert ids(store, ListFilters(with_person=True)) == ["c1"]
    assert sorted(ids(store)) == ["c1", "c2"]


def test_the_in_memory_store_applies_the_round_cap_and_keeps_the_variant():
    from dataclasses import replace
    store = store_with(company(1))
    mail = replace(new_mail(), size_category="small", variant=2)
    for n in range(6):
        assert isinstance(store.reserve(f"s{n}", mail, NOW - timedelta(days=40 * (6 - n))), str)
    assert store.reserve("s9", mail, NOW) == Refusal("round_full", None)
    assert {m.variant for m in store.mails("s0")} == {2}


# Honest addresses (design 2026-11-19, point 3): support@ and the like are never used.
def test_a_company_with_only_an_unfit_address_has_none():
    from datetime import datetime, timezone
    from kaltstart.api.store import InMemoryAppStore, ListFilters
    store = InMemoryAppStore(invitation="code-123")
    store.add_company(company(1), emails=[EmailRow("support@c1.example.ch", "generic", "u")],
                      people=[])
    store.add_company(company(2), emails=[EmailRow("support@c2.example.ch", "generic", "u"),
                                          EmailRow("info@c2.example.ch", "generic", "u")],
                      people=[])
    now = datetime.now(timezone.utc)
    ids = {r.id for r in store.companies(ListFilters(), "s1", now)[0]}
    assert "c1" not in ids and "c2" in ids
    assert store.company("c1") is None
    assert [e.address for e in store.emails("c2")] == ["info@c2.example.ch"]
