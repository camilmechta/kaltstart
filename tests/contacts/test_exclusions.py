import pytest

from kaltstart.contacts.exclusions import normalise_name, person_key, without_excluded
from kaltstart.contacts.models import CompanyResult, FoundEmail, FoundPerson

PAGE = "https://example.ch/team"
ANNA = FoundPerson("Anna Muster", "Founder", ("leadership",), "head", PAGE)
BEN = FoundPerson("Ben Probe", "CTO", ("leadership",), "head", PAGE)
RESULT = CompanyResult(
    company_id="c1", name="Example Robotics", website="https://example.ch",
    size_category="small", pages_fetched=(PAGE,),
    emails=(FoundEmail("anna.muster@example.ch", "personal", PAGE),
            FoundEmail("ben@example.ch", "personal", PAGE),
            FoundEmail("info@example.ch", "generic", PAGE)),
    people=(ANNA, BEN), contact=None, failure=None)


def test_normalise_name():
    assert normalise_name("  Anna   MUSTER ") == "anna muster"


def test_person_key_is_pinned():
    # The same value is computed in SQL by exclude_person (migration 0002).
    assert person_key("c1", "Anna Muster") == (
        "85b0bacf71f2773b11e3eb7f94be447720c15f4cc440166dcb416ec15f682f6b")


@pytest.mark.parametrize("name", ["anna muster", "  Anna   Muster ", "ANNA MUSTER"])
def test_person_key_ignores_case_and_spacing(name):
    assert person_key("c1", name) == person_key("c1", "Anna Muster")


def test_person_key_depends_on_the_company():
    assert person_key("c1", "Anna Muster") != person_key("c2", "Anna Muster")


def test_excluded_person_and_their_address_are_dropped():
    emails, people = without_excluded(RESULT, frozenset({person_key("c1", "Anna Muster")}))
    assert [p.name for p in people] == ["Ben Probe"]
    assert [e.address for e in emails] == ["ben@example.ch", "info@example.ch"]


def test_nothing_excluded_returns_everything():
    assert without_excluded(RESULT, frozenset()) == (RESULT.emails, RESULT.people)


def test_a_key_of_another_company_excludes_nobody():
    keys = frozenset({person_key("c2", "Anna Muster")})
    assert without_excluded(RESULT, keys) == (RESULT.emails, RESULT.people)


@pytest.mark.parametrize("name", [
    "Anna Muster",            # a non-breaking space, common on web pages
    "\tAnna Muster\n",             # a tab and a line break around the name
    "Anna Muster",            # a thin space
    "Anna 　 Muster",          # an ideographic space among ordinary ones
])
def test_person_key_treats_every_kind_of_space_alike(name):
    assert person_key("c1", name) == person_key("c1", "Anna Muster")


def test_person_key_does_not_depend_on_how_an_accent_is_encoded():
    composed = "Änna Ölz"              # Ä and Ö as one character each
    decomposed = "Änna Ölz"           # a letter followed by a combining mark
    assert person_key("c1", composed) == person_key("c1", decomposed)


def test_person_key_of_a_name_with_accents_is_pinned():
    # Checked against SQL by the owner after migration 0003.
    assert person_key("c1", "ÄNNA ÖLZ") == (
        "78e1304e99cfaadd34274d21dd9de6c5dd52a195b890d7cba79669db363b3ada")


# --- addresses of a removed person ------------------------------------------

from kaltstart.contacts.exclusions import (  # noqa: E402
    contact_key, is_excluded_address, name_address_keys)


def test_contact_key_is_pinned():
    # Checked against SQL by the owner after migration 0003.
    assert contact_key("c1", "last:muster") == (
        "7ec406f609f0373eedb8fd52e1e7616fb9604c9bdde9578b3ae31490951ee9f2")


@pytest.mark.parametrize("address", [
    "anna.muster@example.ch", "muster@example.ch", "a-muster@example.ch",
    "anna@example.ch", "amuster@example.ch", "ANNA.MUSTER@example.ch"])
def test_the_address_forms_of_a_removed_person_are_excluded(address):
    keys = name_address_keys("c1", "  Anna   MUSTER ")
    assert is_excluded_address("c1", address, keys)


@pytest.mark.parametrize("address", [
    "info@example.ch", "annabelle@example.ch", "ben.probe@example.ch", "mustermann@example.ch"])
def test_other_addresses_are_kept(address):
    assert not is_excluded_address("c1", address, name_address_keys("c1", "Anna Muster"))


def test_address_keys_belong_to_one_company():
    keys = name_address_keys("c2", "Anna Muster")
    assert not is_excluded_address("c1", "anna.muster@example.ch", keys)


def test_a_removed_persons_address_is_dropped_even_when_typed_generic():
    # The person is no longer on the team page, so her address is now "generic".
    result = CompanyResult(
        company_id="c1", name="Example Robotics", website="https://example.ch",
        size_category="small", pages_fetched=(PAGE,),
        emails=(FoundEmail("anna.muster@example.ch", "generic", PAGE),
                FoundEmail("info@example.ch", "generic", PAGE)),
        people=(BEN,), contact=None, failure=None)
    emails, people = without_excluded(result, frozenset(),
                                      name_address_keys("c1", "Anna Muster"))
    assert [e.address for e in emails] == ["info@example.ch"]
    assert people == (BEN,)
