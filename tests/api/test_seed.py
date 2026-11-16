from datetime import datetime, timezone

from kaltstart.api.seed import seeded_store
from kaltstart.api.store import ListFilters

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
EXAMPLE_DOMAINS = (".example.ch", ".example.de", ".example.com", ".example.at")


def test_the_seed_covers_the_three_countries_with_invented_data():
    store = seeded_store(NOW)
    rows, total = store.companies(ListFilters(), "dev", NOW)
    assert total >= 30
    assert {r.country for r in rows} == {"Switzerland", "Germany", "Austria"}
    for row in rows:
        for email in store.emails(row.id):
            assert email.address.endswith(EXAMPLE_DOMAINS), email.address
        for person in store.people(row.id):
            assert "example" in person.source_url


def test_the_seed_has_a_full_company_hidden_from_the_list():
    store = seeded_store(NOW)
    listed = {r.id for r in store.companies(ListFilters(), "dev", NOW)[0]}
    assert store.company("full") is not None and "full" not in listed


def test_the_seed_is_the_same_every_time():
    first = seeded_store(NOW).companies(ListFilters(), "dev", NOW)[0]
    second = seeded_store(NOW).companies(ListFilters(), "dev", NOW)[0]
    assert first == second


def test_company_names_are_unique():
    store = seeded_store(NOW)
    rows, total = store.companies(ListFilters(), "dev", NOW)
    names = [r.name for r in rows]
    assert len(set(names)) == len(names) == total
