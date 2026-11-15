"""People and companies that asked not to be listed.

An excluded person is stored as a key, never as a name: the list of people
who asked to disappear must not itself be a list of names. The same key is
computed in SQL by `exclude_person` (migration 0002).
"""

import hashlib

from kaltstart.contacts.models import CompanyResult, FoundEmail, FoundPerson
from kaltstart.contacts.selection import address_owner


def normalise_name(name: str) -> str:
    """Trimmed, inner whitespace collapsed to one space, lower case."""
    return " ".join(name.split()).lower()


def person_key(company_id: str, name: str) -> str:
    """SHA-256 of the company id, a line break and the normalised name."""
    return hashlib.sha256(f"{company_id}\n{normalise_name(name)}".encode("utf-8")).hexdigest()


def without_excluded(
        result: CompanyResult, person_keys: frozenset[str],
) -> tuple[tuple[FoundEmail, ...], tuple[FoundPerson, ...]]:
    """The emails and people of `result` without the excluded people and
    without the personal addresses that belong to them."""
    excluded = [p for p in result.people
                if person_key(result.company_id, p.name) in person_keys]
    if not excluded:
        return result.emails, result.people
    people = tuple(p for p in result.people if p not in excluded)
    emails = tuple(e for e in result.emails
                   if not (e.type == "personal" and address_owner(e.address, excluded)))
    return emails, people
