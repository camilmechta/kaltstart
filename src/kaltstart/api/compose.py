"""Who the mail goes to, decided on the server from the stored contacts
(spec 9b point 4): the form only says which choice the student made."""

from dataclasses import dataclass
from typing import Sequence

from kaltstart.api.store import CompanyRow, EmailRow, PersonRow, Profile, Showcase
from kaltstart.contacts.exclusions import normalise_name, person_key
from kaltstart.contacts.models import FoundEmail, FoundPerson
from kaltstart.contacts.selection import address_owner, choose_contact, choose_person
from kaltstart.mailgen import models as mg

# The student's role, as mailgen spells it, to the spelling of contacts.selection.
ROLE_TO_SELECTION = {"product": "product", "growth": "growth", "data": "data",
                     "operations": "ops", "business_development": "bd"}
CHOICES = ("suggested", "other_on_list", "typed", "team")
MAX_TYPED_NAME = 40


class NoAddress(ValueError):
    """The company publishes no address this choice can use."""


@dataclass(frozen=True)
class Recipient:
    person_name: str | None
    person_source_url: str | None
    address: str
    address_type: str
    person_choice: str
    person_key: str | None


def _found(people: Sequence[PersonRow]) -> list[FoundPerson]:
    return [FoundPerson(p.name, p.title, p.categories, p.level, p.source_url) for p in people]


def _found_emails(emails: Sequence[EmailRow]) -> list[FoundEmail]:
    return [FoundEmail(e.address, e.type, e.source_url) for e in emails]


def suggested(company: CompanyRow, people: Sequence[PersonRow],
              profile: Profile | None) -> PersonRow | None:
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
           typed_name: str | None = None) -> Recipient:
    if choice not in CHOICES:
        raise ValueError(f"unknown choice: {choice}")
    if choice == "team":
        email = _shared_address(emails)
        return Recipient(None, None, email.address, email.type, "team", None)
    if choice == "typed":
        name = " ".join((typed_name or "").split())
        if not name or len(name) > MAX_TYPED_NAME:
            raise ValueError("a name of 1 to 40 characters is required")
        email = _shared_address(emails)
        return Recipient(name, None, email.address, email.type, "typed",
                         person_key(company.id, name))

    if choice == "suggested":
        person = suggested(company, people, profile)
        if person is None:
            raise ValueError("no person is suggested for this company")
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
        own = next((e for e in emails if e.type == "personal"
                    and address_owner(e.address, _found([person]))), None)
        email = own or _shared_address(emails)
    return Recipient(person.name, person.source_url, email.address, email.type, choice,
                     person_key(company.id, person.name))


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
        chosen_example=index)
    return (student,
            mg.Company(company.id, company.name, company.country, company.city, None),
            mg.Round(company.stage, company.amount_eur, company.amount_native,
                     company.currency, company.investors, company.size_category),
            mg.Contact(recipient.address, recipient.address_type, recipient.person_name))
