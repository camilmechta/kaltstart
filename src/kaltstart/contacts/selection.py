"""Type of an address, and the contact to propose for a company."""

import re
from typing import Sequence

from kaltstart.contacts.models import FoundEmail, FoundFounder, ProposedContact

CAREERS_LOCAL_PARTS = ("careers", "career", "jobs", "talent", "hr", "karriere",
                       "recruiting")


def _owner(address: str, founders: Sequence[FoundFounder]) -> FoundFounder | None:
    """The founder whose name the local part carries, if any."""
    local = address.split("@", 1)[0].lower()
    tokens = [t for t in re.split(r"[._-]", local) if t]
    for founder in founders:
        words = founder.name.lower().split()
        first, last = words[0], words[-1]
        if first in tokens or last in tokens or local == first[0] + last:
            return founder
    return None


def address_type(address: str, founders: Sequence[FoundFounder]) -> str:
    """`personal`, `careers` or `generic`. Personal needs a founder found."""
    if _owner(address, founders):
        return "personal"
    if address.split("@", 1)[0].lower() in CAREERS_LOCAL_PARTS:
        return "careers"
    return "generic"


def _first(emails: Sequence[FoundEmail], type_: str) -> FoundEmail | None:
    return next((e for e in emails if e.type == type_), None)


def choose_contact(emails: Sequence[FoundEmail], founders: Sequence[FoundFounder],
                   size_category: str) -> ProposedContact | None:
    """Contact and confidence, following section 7.2 of the design spec."""
    personal = _first(emails, "personal")
    careers = _first(emails, "careers")
    generic = _first(emails, "generic")
    if size_category == "small":
        if personal:
            owner = _owner(personal.address, founders)
            return ProposedContact(personal.address, owner.name if owner else None, "high")
        # At a small company the general inbox is the one founders read.
        chosen = generic or careers
        if chosen is None:
            return None
        founder_name = founders[0].name if founders else None
        confident = chosen.type == "careers" or founder_name is not None
        return ProposedContact(chosen.address, founder_name,
                               "medium" if confident else "low")
    if careers:
        return ProposedContact(careers.address, None, "medium")
    if generic:
        return ProposedContact(generic.address, None, "low")
    return None
