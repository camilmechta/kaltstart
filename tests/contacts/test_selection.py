import pytest

from kaltstart.contacts.models import FoundEmail, FoundFounder, ProposedContact
from kaltstart.contacts.selection import CAREERS_LOCAL_PARTS, address_type, choose_contact

ANNA = FoundFounder("Anna Muster", "Founder", "https://example.ch/team")


def test_careers_local_parts():
    assert CAREERS_LOCAL_PARTS == (
        "careers", "career", "jobs", "talent", "hr", "karriere", "recruiting")


@pytest.mark.parametrize("address,founders,expected", [
    ("anna@example.ch", [ANNA], "personal"),
    ("a.muster@example.ch", [ANNA], "personal"),
    ("amuster@example.ch", [ANNA], "personal"),
    ("anna.muster@example.ch", [], "generic"),     # no founder found: never guessed as personal
    ("jobs@example.ch", [ANNA], "careers"),
    ("karriere@example.ch", [], "careers"),
    ("hello@example.ch", [ANNA], "generic"),
    ("info@example.ch", [], "generic"),
    ("joanna@example.ch", [ANNA], "generic"),      # contains "anna" but is another name
])
def test_address_type(address, founders, expected):
    assert address_type(address, founders) == expected


def mail(address, type_):
    return FoundEmail(address, type_, "https://example.ch/kontakt")


PERSONAL, CAREERS, GENERIC = (mail("anna@example.ch", "personal"),
                              mail("jobs@example.ch", "careers"),
                              mail("info@example.ch", "generic"))


@pytest.mark.parametrize("emails,founders,size,expected", [
    ([GENERIC, CAREERS, PERSONAL], [ANNA], "small", ProposedContact("anna@example.ch", "Anna Muster", "high")),
    ([GENERIC, CAREERS], [ANNA], "small", ProposedContact("info@example.ch", "Anna Muster", "medium")),
    ([CAREERS], [ANNA], "small", ProposedContact("jobs@example.ch", "Anna Muster", "medium")),
    ([GENERIC], [], "small", ProposedContact("info@example.ch", None, "low")),
    ([GENERIC, CAREERS], [], "small", ProposedContact("info@example.ch", None, "low")),
    ([CAREERS], [], "small", ProposedContact("jobs@example.ch", None, "medium")),
    ([GENERIC, CAREERS, PERSONAL], [ANNA], "medium", ProposedContact("jobs@example.ch", None, "medium")),
    ([GENERIC, PERSONAL], [ANNA], "large", ProposedContact("info@example.ch", None, "low")),
    ([PERSONAL], [ANNA], "large", None),
    ([], [ANNA], "small", None),
])
def test_choose_contact(emails, founders, size, expected):
    assert choose_contact(emails, founders, size) == expected


def test_personal_contact_names_the_founder_the_address_belongs_to():
    jonas = FoundFounder("Jonas Beispiel", "Co-Founder", "https://example.ch/team")
    emails = [mail("jonas@example.ch", "personal")]
    assert choose_contact(emails, [ANNA, jonas], "small") == ProposedContact(
        "jonas@example.ch", "Jonas Beispiel", "high")
