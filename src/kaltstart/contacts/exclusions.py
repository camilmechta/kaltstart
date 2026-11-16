"""People and companies that asked not to be listed.

An excluded person is stored as keys, never as a name: the list of people
who asked to disappear must not itself be a list of names. A person has one
key for the name and three for the forms an address of theirs takes, so that
their address is dropped whatever type it is read as. The same keys are
computed in SQL by `exclude_person` (migration 0003).
"""

import hashlib
import re
import unicodedata

from kaltstart.contacts.models import CompanyResult, FoundEmail, FoundPerson
from kaltstart.contacts.selection import address_owner


def normalise_name(name: str) -> str:
    """Unicode NFC, every kind of whitespace collapsed to one space, trimmed,
    lower case. `contact_normalise_name` in SQL (migration 0003) does the same."""
    return " ".join(unicodedata.normalize("NFC", name).split()).lower()


def contact_key(company_id: str, value: str) -> str:
    """SHA-256 of the company id, a line break and `value`, in hexadecimal."""
    return hashlib.sha256(f"{company_id}\n{value}".encode("utf-8")).hexdigest()


def person_key(company_id: str, name: str) -> str:
    """The key of a person: `contact_key` of the normalised name."""
    return contact_key(company_id, normalise_name(name))


def name_address_keys(company_id: str, name: str) -> frozenset[str]:
    """Keys of the address forms of a person, as `selection.address_owner`
    reads them: the last name as a part of the local part, or the local part
    being exactly the first name, or the first initial and the last name."""
    words = normalise_name(name).split()
    first, last = words[0], words[-1]
    return frozenset(contact_key(company_id, value) for value in
                     (f"last:{last}", f"whole:{first}", f"whole:{first[0]}{last}"))


def is_excluded_address(company_id: str, address: str, address_keys: frozenset[str]) -> bool:
    local = address.split("@", 1)[0].lower()
    parts = [part for part in re.split(r"[._-]", local) if part]
    return (contact_key(company_id, f"whole:{local}") in address_keys
            or any(contact_key(company_id, f"last:{part}") in address_keys for part in parts))


def without_excluded(
        result: CompanyResult, person_keys: frozenset[str],
        address_keys: frozenset[str] = frozenset(),
) -> tuple[tuple[FoundEmail, ...], tuple[FoundPerson, ...]]:
    """The emails and people of `result` without the excluded people, and
    without their addresses: those that belong to an excluded person read on
    the page, and those whose form matches an address key, whatever their type."""
    excluded = [p for p in result.people
                if person_key(result.company_id, p.name) in person_keys]
    if not excluded and not address_keys:
        return result.emails, result.people
    people = tuple(p for p in result.people if p not in excluded)
    emails = tuple(e for e in result.emails
                   if not (e.type == "personal" and address_owner(e.address, excluded))
                   and not is_excluded_address(result.company_id, e.address, address_keys))
    return emails, people
