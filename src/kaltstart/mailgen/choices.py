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


def axes(k: int) -> tuple[int, int, int, int, int]:
    """The wording of each axis (subject, opening, lead-in, close, order) for
    the k-th mail kept for a company and round (k = 0 for the first). Any two
    of the first three differ on every three-wording axis; the first 27 never
    share subject, opening and lead-in at once."""
    q, t = k // 3, k // 9
    return (k % 3, (k + q) % 3, (k + 2 * q + t) % 3, (k + 2 * t) % 3, q % 2)


def _kind(language: str, request: str, capital: bool) -> str:
    if language == "en":
        word = "internship" if request == "internship" else "part-time role"
        return word.capitalize() if capital else word
    return "Praktikum" if request == "internship" else "Teilzeit"


def _candidates(style: str, language: str, company: str, round: str, role: str,
                request: str, wording: int = 0) -> list[str]:
    """Subjects from the fullest to the shortest: the round goes first, then
    the role; the last one fits whatever the company name. Three wordings per
    style; wording 0 is the one of the reference mails."""
    kind, Kind = _kind(language, request, False), _kind(language, request, True)
    if language == "en":
        at = f"{Kind} at {company}"
        return {
            "direct": ([f"{company} {kind}?", f"{Kind}?"],
                       [f"{Kind} at {company}?", f"{Kind}?"],
                       [f"{role} {kind} at {company}?", f"{Kind} at {company}?", f"{Kind}?"]),
            "round": ([f"After your {round}: {role} at {company}", f"{role} at {company}", at,
                       f"{Kind}?"],
                      [f"{role} at {company}, after your {round}", f"{role} at {company}", at,
                       f"{Kind}?"],
                      [f"Joining {company} after your {round}?", f"{role} at {company}", at,
                       f"{Kind}?"]),
            "formal": ([f"Application: {role} {kind} at {company}",
                        f"Application: {kind} at {company}", f"Application: {kind}"],
                       [f"{role} {kind}: application to {company}",
                        f"Application to {company}", f"Application: {kind}"],
                       [f"Spontaneous application: {role} {kind} at {company}",
                        f"Spontaneous application to {company}", f"Application: {kind}"]),
        }[style][wording]
    at = f"{Kind} bei {company}"
    compound = f"{role.replace(' ', '-')}-{Kind}"
    return {
        "direct": ([f"{Kind} bei {company}?", f"{Kind}?"],
                   [f"{company}: {Kind}?", f"{Kind}?"],
                   [f"{compound} bei {company}?", f"{Kind} bei {company}?", f"{Kind}?"]),
        "round": ([f"Nach eurer {round}: {role} bei {company}", f"{role} bei {company}", at,
                   f"{Kind}?"],
                  [f"{role} bei {company} nach eurer {round}", f"{role} bei {company}", at,
                   f"{Kind}?"],
                  [f"Mitarbeit im Bereich {role} bei {company}?", f"{role} bei {company}", at,
                   f"{Kind}?"]),
        "formal": ([f"Bewerbung: {compound} bei {company}", f"Bewerbung: {Kind} bei {company}",
                    f"Bewerbung: {Kind}"],
                   [f"Initiativbewerbung: {compound} bei {company}",
                    f"Initiativbewerbung bei {company}", f"Bewerbung: {Kind}"],
                   [f"{compound} bei {company}: Bewerbung", f"Bewerbung bei {company}",
                    f"Bewerbung: {Kind}"]),
    }[style][wording]


def subject(style: str, language: str, company: str, round: str, role: str,
            request: str, wording: int = 0) -> str:
    candidates = _candidates(style, language, company, round, role, request, wording)
    return next(text for text in candidates if len(text) <= MAX_SUBJECT_CHARS)


def suggested_style(contact: Contact, round: Round) -> str:
    """Formal for a large company reached only through an HR or general
    address; Direct otherwise. The student can always change it."""
    if (contact.person_name is None and contact.address_type in ("careers", "generic")
            and round.size_category == "large"):
        return "formal"
    return "direct"
