import pytest

from kaltstart.contacts.models import FoundEmail, FoundPerson, ProposedContact
from kaltstart.contacts.selection import (
    CAREERS_LOCAL_PARTS, address_type, choose_contact, choose_person, read_type, usable_address)


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
        "careers", "career", "jobs", "talent", "hr", "karriere", "recruiting",
        # Recruiting addresses left as general before (D110).
        "work", "hiring", "join", "joinus", "apply", "application", "applications",
        "bewerbung", "bewerbungen", "recruitment", "recruit", "talents")


@pytest.mark.parametrize("address", [
    "work@example.ch", "hiring@example.ch", "join@example.de", "join-us@example.de",
    "joinus@example.de", "join.us@example.de", "Bewerbung@example.de", "bewerbungen@example.de",
    "apply@example.com", "recruitment@example.com", "jobs+de@example.de"])
def test_recruiting_addresses_are_careers(address):
    assert address_type(address, []) == "careers"


@pytest.mark.parametrize("address", [
    "workshop@example.ch", "network@example.ch", "info@example.ch", "joiner@example.de",
    "teamwork@example.de", "hello@example.com"])
def test_words_that_only_contain_a_recruiting_word_stay_general(address):
    assert address_type(address, []) == "generic"


@pytest.mark.parametrize("address,stored,expected", [
    ("work@example.ch", "generic", "careers"),       # read before D110, upgraded when read
    ("bewerbung@example.de", "generic", "careers"),
    ("info@example.ch", "generic", "generic"),
    ("jobs@example.ch", "careers", "careers"),
    ("work@example.ch", "personal", "personal"),     # never changes a person's address
])
def test_the_type_read_upgrades_an_old_general_recruiting_address(address, stored, expected):
    assert read_type(address, stored) == expected


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


def test_the_only_address_belongs_to_another_person_kept():
    # Found by the review: the company must not vanish from the student list.
    lena = person("Lena Beispiel", "Head of Marketing", ("growth",))
    own = FoundEmail("lena@example.ch", "personal", "https://example.ch/team")
    assert choose_contact([own], None, [lena]) == ProposedContact(
        "lena@example.ch", "Lena Beispiel", "high")
    assert choose_contact([own], FOUNDER, [FOUNDER, lena]) == ProposedContact(
        "lena@example.ch", "Lena Beispiel", "high")
    # Without knowing whose address it is, nothing is proposed.
    assert choose_contact([own], None) is None


# Technical roles (technical roles design, section 6).
HEAD_ENG = person("Tim Muster", "Head of Engineering", ("engineering",))
HEAD_RND = person("Eva Probe", "Head of R&D", ("rnd",))


def test_a_technical_role_finds_its_head():
    assert choose_person([FOUNDER, CTO, HEAD_ENG], "software", "small") == HEAD_ENG
    assert choose_person([FOUNDER, CTO, HEAD_RND], "rnd", "medium") == HEAD_RND


def test_a_technical_role_falls_back_to_the_cto_at_a_small_company():
    assert choose_person([FOUNDER, CTO], "software", "small") == CTO
    assert choose_person([FOUNDER, CTO], "rnd", "small") == CTO


def test_business_roles_still_prefer_the_founder():
    assert choose_person([CTO, FOUNDER], "growth", "small") == FOUNDER


def test_a_technical_role_at_a_larger_company_goes_to_recruiting():
    assert choose_person([CTO, HR], "software", "large") == HR


# Honest addresses (design 2026-11-19, point 3).
@pytest.mark.parametrize("local", [
    "support", "help", "helpdesk", "service", "customerservice", "kundenservice",
    "noreply", "no-reply", "donotreply", "privacy", "datenschutz", "dpo", "gdpr",
    "press", "presse", "media", "pr", "legal", "billing", "invoices", "rechnung",
    "accounting", "buchhaltung", "orders", "shop", "newsletter", "webmaster",
    "postmaster", "security", "compliance", "returns", "feedback", "api", "dev"])
def test_addresses_not_meant_for_an_application(local):
    from kaltstart.contacts.selection import usable_address
    assert not usable_address(f"{local}@example.ch")
    assert not usable_address(f"{local.upper()}@example.ch")


@pytest.mark.parametrize("local", ["info", "hello", "contact", "jobs", "team", "office",
                                   "kontakt", "anna.muster", "careers", "hr"])
def test_addresses_fit_for_an_application(local):
    from kaltstart.contacts.selection import usable_address
    assert usable_address(f"{local}@example.ch")


@pytest.mark.parametrize("address", ["no_reply@example.ch", "no.reply@example.ch",
                                     "noreply+news@example.ch", "support-de@example.ch",
                                     "support.ch@example.ch", "Customer.Service@example.ch"])
def test_variants_of_unfit_addresses(address):
    from kaltstart.contacts.selection import usable_address
    assert not usable_address(address)


@pytest.mark.parametrize("address", ["info-de@example.ch",
                                     "hello.ch@example.ch", "jobs-ch@example.ch"])
def test_variants_that_stay_usable(address):
    from kaltstart.contacts.selection import usable_address
    assert usable_address(address)



# Seen on the live site (2026-11-19): a refused word glued to another one.
@pytest.mark.parametrize("address", ["customersupport@example.ch", "techsupport@example.ch",
                                     "kundensupport@example.ch", "supportteam@example.ch",
                                     "clientservice@example.ch", "privacyoffice@example.ch",
                                     "billingteam@example.ch", "teamnoreply@example.ch",
                                     "mediarelations@example.ch", "pressoffice@example.ch"])
def test_refused_words_glued_to_another(address):
    from kaltstart.contacts.selection import usable_address
    assert not usable_address(address)


@pytest.mark.parametrize("address", ["skincare@example.ch", "hello@example.ch",
                                     "people@example.ch", "devteam.jobs@example.ch",
                                     "careers@example.ch", "contact@example.ch",
                                     "apply@example.ch", "office@example.ch"])
def test_ordinary_words_are_not_caught(address):
    from kaltstart.contacts.selection import usable_address
    assert usable_address(address)


# Owner's walk-through, 2026-11-20: a sales address was offered. The words come
# from the shared address starts in the live database (each at 3+ companies),
# with their usual German and plural forms.
@pytest.mark.parametrize("local", [
    "sales", "sale", "vertrieb", "verkauf", "marketing", "partners", "partner",
    "partnerships", "partnership", "bizdev", "business", "affiliate", "affiliates",
    "sponsoring", "advertising", "ads", "werbung", "investors", "investor", "ir",
    "events", "booking", "bookings", "reservations", "tickets", "demo", "onboarding",
    "procurement", "purchasing", "einkauf"])
def test_commercial_addresses_are_not_for_an_application(local):
    from kaltstart.contacts.selection import usable_address
    assert not usable_address(f"{local}@example.ch")


@pytest.mark.parametrize("address", ["salesteam@example.ch", "sales-ch@example.ch",
                                     "sales.de@example.ch", "teamsales@example.ch",
                                     "marketingteam@example.ch", "vertrieb-de@example.ch",
                                     "partnerships.eu@example.ch", "procurement-ch@example.ch"])
def test_commercial_words_glued_or_with_a_country(address):
    from kaltstart.contacts.selection import usable_address
    assert not usable_address(address)


@pytest.mark.parametrize("local", ["founders", "hi", "hallo", "hey", "work", "hiring", "join",
                                   "bewerbung", "karriere", "talent", "recruiting"])
def test_the_other_shared_starts_stay_usable(local):
    from kaltstart.contacts.selection import usable_address
    assert usable_address(f"{local}@example.ch")


# Final review, 2026-11-20: surnames such as Rosales or Sales, and <word>.jobs.
@pytest.mark.parametrize("address", ["maria.rosales@example.ch", "anna.sales@example.ch",
                                     "tsales@example.ch", "sale.marco@example.ch"])
def test_a_persons_own_address_is_never_refused_for_a_word(address):
    from kaltstart.contacts.selection import usable_email
    assert usable_email(address, "personal")


@pytest.mark.parametrize("address", ["ir.jobs@example.ch", "sales.jobs@example.ch",
                                     "business.jobs@example.ch", "jobs-sales@example.ch",
                                     "marketing-careers@example.ch"])
def test_an_address_naming_jobs_stays_usable(address):
    from kaltstart.contacts.selection import usable_address
    assert usable_address(address)


@pytest.mark.parametrize("address", ["noreply-jobs@example.ch", "jobs.noreply@example.ch",
                                     "donotreply.careers@example.ch"])
def test_a_no_reply_address_stays_refused_even_with_jobs(address):
    from kaltstart.contacts.selection import usable_address
    assert not usable_address(address)


def test_shared_addresses_are_still_filtered_by_usable_email():
    from kaltstart.contacts.selection import usable_email
    assert not usable_email("sales@example.ch", "generic")
    assert usable_email("info@example.ch", "generic")


@pytest.mark.parametrize("address", [
    "support.work@example.ch", "apply-support@example.ch", "work.sales@example.ch",
    "join.sales@example.ch", "recruit-marketing@example.de"])
def test_a_short_recruiting_word_never_makes_an_unfit_address_usable(address):
    # Review 2026-11-23 (D110): only the long careers words override an unfit word.
    assert not usable_address(address)
