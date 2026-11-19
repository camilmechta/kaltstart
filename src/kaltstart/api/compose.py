"""Who the mail goes to, decided on the server from the stored contacts
(spec 9b point 4): the form only says which choice the student made."""

import re
from dataclasses import dataclass
from typing import Sequence

from kaltstart.api.forms import ROLE_LABELS
from kaltstart.api.store import CompanyRow, EmailRow, PersonRow, Profile, Showcase
from kaltstart.contacts.exclusions import normalise_name, person_key
from kaltstart.contacts.models import FoundEmail, FoundPerson
from kaltstart.contacts.selection import (
    TECHNICAL_ROLES, address_owner, choose_contact, choose_person)
from kaltstart.mailgen import models as mg

# The student's role, as mailgen spells it, to the spelling of contacts.selection.
ROLE_TO_SELECTION = {"product": "product", "growth": "growth", "data": "data",
                     "operations": "ops", "business_development": "bd",
                     "software_ai": "software", "rd_hardware": "rnd"}
CHOICES = ("suggested", "other_on_list", "typed", "team")
MAX_TYPED_NAME = 40


class NoAddress(ValueError):
    """The company publishes no address this choice can use."""


class BadAddress(ValueError):
    """The address the student gave does not look like one."""


# One address: no space, one "@", a dot in the domain (honest addresses, point 4).
_ADDRESS = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# Characters no plain address needs: control characters, brackets, quotes,
# separators of other mail headers or of a link.
_ODD = re.compile(r"[\x00-\x1f\x7f<>\"(),;:\[\]\\?&]")
MAX_ADDRESS = 254


def student_address(text: str | None) -> str | None:
    """The address the student gave for the person, or None when left empty."""
    address = (text or "").strip()
    if not address:
        return None
    if len(address) > MAX_ADDRESS or not _ADDRESS.fullmatch(address) or _ODD.search(address):
        raise BadAddress("not an address")
    return address


@dataclass(frozen=True)
class Recipient:
    person_name: str | None
    person_source_url: str | None
    address: str
    address_type: str
    person_choice: str
    person_key: str | None
    person_title: str | None = None


def _found(people: Sequence[PersonRow]) -> list[FoundPerson]:
    return [FoundPerson(p.name, p.title, p.categories, p.level, p.source_url) for p in people]


def _found_emails(emails: Sequence[EmailRow]) -> list[FoundEmail]:
    return [FoundEmail(e.address, e.type, e.source_url) for e in emails]


def names_people(company: CompanyRow) -> bool:
    """False for a large company (Series B and later): applications go through
    its careers or general address, and no person is suggested or listed
    (owner, 2026-11-19). A student may still name someone they know."""
    return company.size_category != "large"


def suggested(company: CompanyRow, people: Sequence[PersonRow],
              profile: Profile | None) -> PersonRow | None:
    if not names_people(company):
        return None
    role = ROLE_TO_SELECTION.get(profile.target_role or "") if profile else None
    chosen = choose_person(_found(people), role, company.size_category)
    return next((p for p in people if chosen and p.name == chosen.name), None)


def _first_of(emails: Sequence[EmailRow], kind: str) -> EmailRow | None:
    return next((e for e in emails if e.type == kind), None)


def _shared_address(emails: Sequence[EmailRow]) -> EmailRow:
    """The careers address, else the general one; never somebody's own."""
    email = _first_of(emails, "careers") or _first_of(emails, "generic")
    if email is None:
        raise NoAddress("no careers or general address")
    return email


def choose(company: CompanyRow, people: Sequence[PersonRow], emails: Sequence[EmailRow],
           profile: Profile | None, choice: str, *, person_index: int | None = None,
           typed_name: str | None = None, their_address: str | None = None) -> Recipient:
    if choice not in CHOICES:
        raise ValueError(f"unknown choice: {choice}")
    given = student_address(their_address) if choice != "team" else None
    if choice in ("suggested", "other_on_list") and not names_people(company):
        raise ValueError("no person is listed at a large company")
    if choice == "team":
        email = _shared_address(emails)
        return Recipient(None, None, email.address, email.type, "team", None)
    if choice == "typed":
        name = " ".join((typed_name or "").split())
        if not name or len(name) > MAX_TYPED_NAME:
            raise ValueError("a name of 1 to 40 characters is required")
        if given:
            return Recipient(name, None, given, "student", "typed", person_key(company.id, name))
        email = _shared_address(emails)
        return Recipient(name, None, email.address, email.type, "typed",
                         person_key(company.id, name))

    if choice == "suggested":
        person = suggested(company, people, profile)
        if person is None:
            raise ValueError("no person is suggested for this company")
        if given:
            return Recipient(person.name, person.source_url, given, "student", choice,
                             person_key(company.id, person.name), person.title)
        contact = choose_contact(_found_emails(emails), _found([person])[0], _found(people))
        if contact is None:
            raise NoAddress("no address")
        if contact.person_name and normalise_name(contact.person_name) != normalise_name(person.name):
            # The only address belongs to somebody else: never greet the wrong person.
            raise NoAddress("only another person's address")
        email = next(e for e in emails if e.address == contact.address)
    else:
        if person_index is None or not 0 <= person_index < len(people):
            raise ValueError("unknown person")
        person = people[person_index]
        if given:
            return Recipient(person.name, person.source_url, given, "student", choice,
                             person_key(company.id, person.name), person.title)
        own = next((e for e in emails if e.type == "personal"
                    and address_owner(e.address, _found([person]))), None)
        email = own or _shared_address(emails)
    return Recipient(person.name, person.source_url, email.address, email.type, choice,
                     person_key(company.id, person.name), person.title)


def where_it_goes(company_name: str, person_name: str, address_type: str) -> str:
    """Where a mail to a named person goes, said before it is kept (honest
    addresses, 2026-11-19); the address itself shows once kept (D77)."""
    from kaltstart.mailgen.generator import first_name
    first = first_name(person_name)
    if address_type == "personal":
        return f"Goes to {first}'s own address."
    if address_type == "student":
        return "Goes to the address you gave."
    kind = "careers" if address_type == "careers" else "general"
    return (f"Goes to {company_name}'s {kind} address: {first}'s own address is not "
            "published. A PS at the end asks that it reach them.")


def to_mailgen(profile: Profile, showcases: Sequence[Showcase], company: CompanyRow,
               recipient: Recipient, chosen_showcase: int = 1):
    """The inputs of mailgen.generate."""
    ordered = sorted(showcases, key=lambda s: s.position)
    examples = tuple(mg.Example(s.text_en, s.text_de) for s in ordered)
    index = next((i for i, s in enumerate(ordered) if s.position == chosen_showcase), 0)
    student = mg.Student(
        id=profile.id, first_name=profile.first_name, last_name=profile.last_name,
        programme=profile.programme, languages=profile.languages,
        role=profile.target_role or "", request=profile.request or "",
        start_date=profile.start_date, duration_months=profile.duration_months,
        workload_percent=profile.workload_percent, link=profile.link, examples=examples,
        chosen_example=index, level=profile.degree_level, attach_cv=profile.attach_cv,
        university=profile.university or "HSG")
    return (student,
            mg.Company(company.id, company.name, company.country, company.city, None),
            mg.Round(company.stage, company.amount_eur, company.amount_native,
                     company.currency, company.investors, company.size_category),
            mg.Contact(recipient.address, recipient.address_type, recipient.person_name,
                       recipient.person_title))


# The categories of contacts.titles for each target role.
_ROLE_CATEGORY = {"product": "product", "growth": "growth", "data": "data",
                  "operations": "operations", "business_development": "sales",
                  "software_ai": "engineering", "rd_hardware": "rnd"}
_CTO = re.compile(r"(?<!\w)(?:cto|chief technology officer)(?!\w)", re.IGNORECASE)


def why(person: PersonRow, profile: Profile | None, company: CompanyRow) -> str:
    """One sentence saying why this person is suggested, following the order
    of contacts.selection.choose_person."""
    role = profile.target_role if profile else None
    if role and _ROLE_CATEGORY.get(role) in person.categories:
        return (f"Their title, {person.title}, matches your target role: "
                f"{ROLE_LABELS[role]}.")
    if "recruiting" in person.categories and company.size_category != "small":
        return "At a company this size, the recruiting team handles applications."
    if ROLE_TO_SELECTION.get(role or "") in TECHNICAL_ROLES and _CTO.search(person.title):
        return "At a small company, the CTO reads applications for technical roles."
    return ("At a small company, the founders and the leadership read applications "
            "themselves.")
