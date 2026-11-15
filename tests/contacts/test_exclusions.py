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
