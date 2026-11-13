import pytest

from kaltstart.contacts.models import FoundEmail, FoundPerson, ProposedContact
from kaltstart.contacts.selection import (
    CAREERS_LOCAL_PARTS, address_type, choose_contact, choose_person)


def person(name, title, categories, level="head"):
    return FoundPerson(name, title, categories, level, "https://example.ch/team")


FOUNDER = person("Anna Muster", "Co-Founder & CEO", ("leadership",))
CTO = person("Jonas Beispiel", "CTO", ("leadership",))
HEAD_PRODUCT = person("Clara Vorlage", "Head of Product", ("product",))
PM = person("Mia Probe", "Product Manager", ("product",), "manager")
HR = person("Noah Entwurf", "HR Manager", ("recruiting",), "manager")
HEAD_PEOPLE = person("Lea Stark", "Head of People", ("recruiting",))
FOUNDER_PRODUCT = person("Leo Probe", "Co-Founder & Head of Product", ("leadership", "product"))


def test_careers_local_parts():
    assert CAREERS_LOCAL_PARTS == (
        "careers", "career", "jobs", "talent", "hr", "karriere", "recruiting")


@pytest.mark.parametrize("address,people,expected", [
    ("anna@example.ch", [FOUNDER], "personal"),
    ("a.muster@example.ch", [FOUNDER], "personal"),
    ("amuster@example.ch", [FOUNDER], "personal"),
    ("anna.muster@example.ch", [FOUNDER], "personal"),
    ("muster@example.ch", [FOUNDER], "personal"),
    ("clara.vorlage@example.ch", [FOUNDER, HEAD_PRODUCT], "personal"),
    ("anna.muster@example.ch", [], "generic"),      # nobody kept: never guessed as personal
    ("anna.schmidt@example.ch", [FOUNDER], "generic"),
    ("anna-support@example.ch", [FOUNDER], "generic"),
    ("joanna@example.ch", [FOUNDER], "generic"),
    ("jobs@example.ch", [FOUNDER], "careers"),
    ("karriere@example.ch", [], "careers"),
    ("hello@example.ch", [FOUNDER], "generic"),
    ("info@example.ch", [], "generic"),
])
def test_address_type(address, people, expected):
    assert address_type(address, people) == expected


@pytest.mark.parametrize("people,role,size,expected", [
    # 1. Someone in the category of the target role; head before manager; page order.
    ([FOUNDER, PM, HEAD_PRODUCT], "product", "small", HEAD_PRODUCT),
    ([FOUNDER, PM], "product", "large", PM),
    ([FOUNDER, FOUNDER_PRODUCT], "product", "small", FOUNDER_PRODUCT),
    ([FOUNDER, HEAD_PRODUCT, FOUNDER_PRODUCT], "product", "small", HEAD_PRODUCT),
    # 2. Otherwise, small company: leadership; a founder before another leader.
    ([CTO, FOUNDER, HR], "growth", "small", FOUNDER),
    ([CTO, HR], "growth", "small", CTO),
    ([FOUNDER, HEAD_PRODUCT], None, "small", FOUNDER),
    # 3. Otherwise, medium or large: recruiting; head before manager.
    ([FOUNDER, HR, HEAD_PEOPLE], "data", "medium", HEAD_PEOPLE),
    ([FOUNDER, HR], "data", "large", HR),
    ([FOUNDER, HR], None, "large", HR),
    # 4. Otherwise nobody.
    ([FOUNDER], "data", "large", None),
    ([HR], "growth", "small", None),
    ([], "product", "small", None),
])
def test_choose_person(people, role, size, expected):
    assert choose_person(people, role, size) == expected


def test_unknown_target_role_is_treated_as_none():
    assert choose_person([FOUNDER, HEAD_PRODUCT], "astronaut", "small") == FOUNDER


OWN = FoundEmail("clara.vorlage@example.ch", "personal", "https://example.ch/team")
OTHER_PERSONAL = FoundEmail("anna@example.ch", "personal", "https://example.ch/team")
CAREERS = FoundEmail("jobs@example.ch", "careers", "https://example.ch/jobs")
GENERIC = FoundEmail("info@example.ch", "generic", "https://example.ch/")


@pytest.mark.parametrize("emails,chosen,expected", [
    ([GENERIC, CAREERS, OWN], HEAD_PRODUCT, ProposedContact("clara.vorlage@example.ch", "Clara Vorlage", "high")),
    ([GENERIC, CAREERS, OTHER_PERSONAL], HEAD_PRODUCT, ProposedContact("jobs@example.ch", "Clara Vorlage", "medium")),
    ([GENERIC], HEAD_PRODUCT, ProposedContact("info@example.ch", "Clara Vorlage", "medium")),
    ([GENERIC, CAREERS], None, ProposedContact("jobs@example.ch", None, "medium")),
    ([GENERIC], None, ProposedContact("info@example.ch", None, "low")),
    ([OTHER_PERSONAL], HEAD_PRODUCT, None),     # somebody else's address is never proposed
    ([OTHER_PERSONAL], None, None),
    ([], HEAD_PRODUCT, None),
])
def test_choose_contact(emails, chosen, expected):
    assert choose_contact(emails, chosen) == expected
