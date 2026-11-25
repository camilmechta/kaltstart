"""What the mail generator receives and returns."""

from dataclasses import dataclass
from datetime import date

ROLES = ("product", "growth", "data", "operations", "business_development",
         "software_ai", "rd_hardware")
REQUESTS = ("internship", "part_time")
STYLES = ("direct", "round", "formal")
LANGUAGES = ("en", "de")
VARIANTS = 3

# Bounds on what the student types, so that every mail fits in 211 words
# (decision D72; 211 since D113 adds "the" before "University of"). The showcase sentence may be longer than the sentence
# about the company: it is the heart of every mail.
MAX_BODY_WORDS = 211
# A mail to a named person through a shared address ends with a PS saying why
# (honest addresses, 2026-11-19): 25 more words at most, with the longest texts.
MAX_FORWARDED_BODY_WORDS = 235
MAX_EXAMPLE_CHARS = 400
MAX_EXAMPLE_WORDS = 60
MAX_TEXT_CHARS = 200
MAX_TEXT_WORDS = 35
MAX_PROGRAMME_CHARS = 70
MAX_UNIVERSITY_CHARS = 30
MAX_NAME_CHARS = 40


@dataclass(frozen=True)
class Example:
    """A concrete example from the student's profile, in both languages."""
    text_en: str | None
    text_de: str | None


@dataclass(frozen=True)
class Student:
    id: str
    first_name: str
    last_name: str
    programme: str
    languages: tuple[str, ...]
    role: str
    request: str
    start_date: date | None
    duration_months: int | None
    workload_percent: int | None
    link: str | None
    examples: tuple[Example, ...]
    chosen_example: int = 0
    level: str | None = None            # "bachelor" or "master"; None: not given
    attach_cv: bool = False             # the student attaches their CV to the mail
    university: str = "HSG"             # as the student writes it (D85)


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    country: str
    city: str | None
    region: str | None


@dataclass(frozen=True)
class Round:
    stage: str | None
    amount_eur: int | None
    amount_native: float | None
    currency: str | None
    investors: tuple[str, ...]
    size_category: str


@dataclass(frozen=True)
class Contact:
    """`person_name` is set only for a person the student confirmed (D60).
    `address_type` is personal, careers, generic, or student (an address the
    student gave for that person); a named person reached through a careers
    or general address is greeted through the team (design 2026-11-19)."""
    address: str | None
    address_type: str
    person_name: str | None
    person_title: str | None = None


@dataclass(frozen=True)
class Mail:
    subject: str
    body: str
    language: str
    style: str
    used_company_line: bool


class TooLong(ValueError):
    """A text of the student is too long for a mail; `field` names it."""

    def __init__(self, field: str) -> None:
        super().__init__(f"too long: {field}")
        self.field = field


class MissingData(ValueError):
    """A required piece of data is missing; `fields` names each of them."""

    def __init__(self, fields: tuple[str, ...]) -> None:
        super().__init__("missing: " + ", ".join(fields))
        self.fields = fields
