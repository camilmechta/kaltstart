"""Type of an address, the person proposed to a student, and the contact."""

import re
from typing import Sequence

from kaltstart.contacts.models import FoundEmail, FoundPerson, ProposedContact
from kaltstart.contacts.titles import FOUNDER, ROLE_TO_CATEGORY

CAREERS_LOCAL_PARTS = ("careers", "career", "jobs", "talent", "hr", "karriere",
                       "recruiting")


def _owner(address: str, people: Sequence[FoundPerson]) -> FoundPerson | None:
    """The person whose name the local part carries, if any.

    The last name must be there (alone, or with the first name or its
    initial). A first name counts only when it is the whole local part:
    `anna.schmidt@` is not the address of somebody called Anna Muster.
    """
    local = address.split("@", 1)[0].lower()
    tokens = [t for t in re.split(r"[._-]", local) if t]
    for person in people:
        words = person.name.lower().split()
        first, last = words[0], words[-1]
        if last in tokens or local == first or local == first[0] + last:
            return person
    return None


def address_type(address: str, people: Sequence[FoundPerson]) -> str:
    """`personal`, `careers` or `generic`. Personal needs a person kept."""
    if _owner(address, people):
        return "personal"
    if address.split("@", 1)[0].lower() in CAREERS_LOCAL_PARTS:
        return "careers"
    return "generic"


def _heads_first(people: list[FoundPerson]) -> FoundPerson | None:
    # sorted() is stable: among equals, page order is kept.
    return sorted(people, key=lambda p: p.level != "head")[0] if people else None


def choose_person(people: Sequence[FoundPerson], target_role: str | None,
                  size_category: str) -> FoundPerson | None:
    """The person to write to, following section 5 of the people design.

    1. somebody in the category of the student's target role, a head before a
       manager; 2. otherwise, at a small company, a leader, a founder first;
    3. otherwise, at a medium or large one, a recruiter; 4. otherwise nobody.
    """
    category = ROLE_TO_CATEGORY.get(target_role or "")
    if category:
        chosen = _heads_first([p for p in people if category in p.categories])
        if chosen:
            return chosen
    if size_category == "small":
        leaders = [p for p in people if "leadership" in p.categories]
        return sorted(leaders, key=lambda p: not FOUNDER.search(p.title))[0] if leaders else None
    return _heads_first([p for p in people if "recruiting" in p.categories])


def choose_contact(emails: Sequence[FoundEmail], person: FoundPerson | None,
                   people: Sequence[FoundPerson] = ()) -> ProposedContact | None:
    """The address to write to: the person's own if the site publishes it,
    else the careers address, else the general one.

    When the site publishes nothing but the address of another person kept,
    that person is proposed with their address, so that the company does not
    disappear. An address is never proposed to greet somebody it is not.
    """
    if person:
        own = next((e for e in emails if e.type == "personal"
                    and _owner(e.address, [person])), None)
        if own:
            return ProposedContact(own.address, person.name, "high")
    careers = next((e for e in emails if e.type == "careers"), None)
    generic = next((e for e in emails if e.type == "generic"), None)
    chosen = careers or generic
    if chosen is not None:
        confident = chosen.type == "careers" or person is not None
        return ProposedContact(chosen.address, person.name if person else None,
                               "medium" if confident else "low")
    for email in emails:
        owner = _owner(email.address, people) if email.type == "personal" else None
        if owner:
            return ProposedContact(email.address, owner.name, "high")
    return None
