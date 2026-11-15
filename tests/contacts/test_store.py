from datetime import date

from kaltstart.contacts.store import InMemoryContactStore


def email(company_id, address):
    return {"company_id": company_id, "address": address, "type": "generic",
            "source_url": "https://example.ch/", "read_at": "2026-11-15T03:17:00+00:00"}


def person(company_id, name):
    return {"company_id": company_id, "name": name, "title": "Founder",
            "categories": ["leadership"], "level": "head",
            "source_url": "https://example.ch/team", "read_at": "2026-11-15T03:17:00+00:00"}


def store_with_companies():
    store = InMemoryContactStore()
    store.add_company("c1", "Example Robotics", "https://example.ch")
    store.add_company("c2", "Example Foods", "https://example.com")
    store.add_company("c3", "Beispiel GmbH", "https://example.de", country="Germany")
    store.add_company("c4", "No Site AG", None)
    return store


def test_candidates_are_of_the_country_and_have_a_website():
    rows = store_with_companies().candidate_companies("Switzerland")
    assert [r["id"] for r in rows] == ["c1", "c2"]
    assert set(rows[0]) == {"id", "name", "website", "created_at", "contacts_checked_at",
                            "contacts_outcome", "contacts_attempts", "contacts_next_at"}
    assert (rows[0]["contacts_checked_at"], rows[0]["contacts_attempts"]) == (None, 0)


def test_replace_contacts_keeps_only_the_last_reading():
    store = store_with_companies()
    store.replace_contacts("c2", [email("c2", "info@example.com")], [])
    store.replace_contacts("c1", [email("c1", "old@example.ch")], [person("c1", "Anna Muster")])
    store.replace_contacts("c1", [email("c1", "new@example.ch")], [])
    assert [e["address"] for e in store.emails] == ["info@example.com", "new@example.ch"]
    assert store.people == []
    assert store.company_ids_with_contacts() == {"c1", "c2"}


def test_people_alone_count_as_contacts():
    store = store_with_companies()
    store.replace_contacts("c1", [], [person("c1", "Anna Muster")])
    assert store.company_ids_with_contacts() == {"c1"}
    assert store.company_ids_with_people() == {"c1"}


def test_delete_contacts():
    store = store_with_companies()
    store.replace_contacts("c1", [email("c1", "a@example.ch")], [person("c1", "Anna Muster")])
    store.replace_contacts("c2", [email("c2", "info@example.com")], [])
    store.delete_contacts(["c1"])
    assert store.company_ids_with_contacts() == {"c2"}


def test_contact_state_is_visible_in_candidates():
    store = store_with_companies()
    store.set_contact_state("c1", checked_at="2026-11-15T03:17:00+00:00", outcome="ok",
                            attempts=0, next_at="2026-12-15T03:17:00+00:00")
    row = store.candidate_companies("Switzerland")[0]
    assert (row["contacts_checked_at"], row["contacts_outcome"], row["contacts_attempts"],
            row["contacts_next_at"]) == ("2026-11-15T03:17:00+00:00", "ok", 0,
                                         "2026-12-15T03:17:00+00:00")


def test_rounds_since_includes_the_cutoff_day():
    store = store_with_companies()
    store.rounds += [{"company_id": "c1", "date": "2025-11-15"},
                     {"company_id": "c2", "date": "2025-11-14"}]
    assert store.company_ids_with_round_since(date(2025, 11, 15)) == {"c1"}


def test_exclusions_and_runs():
    store = store_with_companies()
    store.excluded.append({"company_id": "c2", "person_key": None})
    assert store.exclusions() == [{"company_id": "c2", "person_key": None}]
    store.record_contact_run({"status": "success"})
    assert store.runs == [{"status": "success"}]
