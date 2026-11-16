"""What the mail generator receives and returns."""

from dataclasses import dataclass
from datetime import date

ROLES = ("product", "growth", "data", "operations", "business_development")
REQUESTS = ("internship", "part_time")
STYLES = ("direct", "round", "formal")
LANGUAGES = ("en", "de")


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
    """`person_name` is set only for a person the student confirmed (D60)."""
    address: str | None
    address_type: str
    person_name: str | None


@dataclass(frozen=True)
class Mail:
    subject: str
    body: str
    language: str
    style: str
    used_company_line: bool


class MissingData(ValueError):
    """A required piece of data is missing; `fields` names each of them."""

    def __init__(self, fields: tuple[str, ...]) -> None:
        super().__init__("missing: " + ", ".join(fields))
        self.fields = fields
