"""The choices the generator makes by itself: which opening wording, which
subject, and which style to suggest."""

import hashlib

from kaltstart.mailgen.models import Contact, Round

MAX_SUBJECT_CHARS = 60
VARIANTS = 3


def variant(student_id: str, company_id: str) -> int:
    """Stable across runs and machines (not Python's salted `hash`): the same
    student gets the same wording for a company, two students usually differ."""
    digest = hashlib.sha256(f"{student_id}\n{company_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % VARIANTS


def _kind(language: str, request: str, capital: bool) -> str:
    if language == "en":
        word = "internship" if request == "internship" else "part-time role"
        return word.capitalize() if capital else word
    return "Praktikum" if request == "internship" else "Teilzeit"


def _candidates(style: str, language: str, company: str, round: str, role: str,
                request: str) -> list[str]:
    """Subjects from the fullest to the shortest: the round goes first, then
    the role; the last one fits whatever the company name."""
    kind, Kind = _kind(language, request, False), _kind(language, request, True)
    if language == "en":
        at = f"{Kind} at {company}"
        return {
            "direct": [f"{company} {kind}?", f"{Kind}?"],
            "round": [f"After your {round}: {role} at {company}", f"{role} at {company}", at,
                      f"{Kind}?"],
            "formal": [f"Application: {role} {kind} at {company}",
                       f"Application: {kind} at {company}", f"Application: {kind}"],
        }[style]
    at = f"{Kind} bei {company}"
    return {
        "direct": [f"{Kind} bei {company}?", f"{Kind}?"],
        "round": [f"Nach eurer {round}: {role} bei {company}", f"{role} bei {company}", at,
                  f"{Kind}?"],
        "formal": [f"Bewerbung: {role.replace(' ', '-')}-{Kind} bei {company}", f"Bewerbung: {Kind} bei {company}",
                   f"Bewerbung: {Kind}"],
    }[style]


def subject(style: str, language: str, company: str, round: str, role: str,
            request: str) -> str:
    candidates = _candidates(style, language, company, round, role, request)
    return next(text for text in candidates if len(text) <= MAX_SUBJECT_CHARS)


def suggested_style(contact: Contact, round: Round) -> str:
    """Formal for a large company reached only through an HR or general
    address; Direct otherwise. The student can always change it."""
    if (contact.person_name is None and contact.address_type in ("careers", "generic")
            and round.size_category == "large"):
        return "formal"
    return "direct"
