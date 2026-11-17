"""What the app reads and writes, and an in-memory version for tests and the
--dev mode. The listing rules (spec 7.2) live in `eligible`, shared by every
store so they cannot drift apart."""

import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Protocol, Sequence

from kaltstart.api import rules
from kaltstart.api.rules import MailRecord, Refusal

PAGE_SIZE = 50
RECENT_ROUND_DAYS = 365
STATUSES = ("generated", "copied", "sent", "human_reply", "positive_reply", "abandoned")


@dataclass(frozen=True)
class Profile:
    id: str
    first_name: str = ""
    last_name: str = ""
    programme: str = ""
    degree_level: str | None = None       # "bachelor" or "master"
    languages: tuple[str, ...] = ("en",)
    target_role: str | None = None
    request: str | None = None
    start_date: date | None = None
    duration_months: int | None = None
    workload_percent: int | None = None
    link: str | None = None
    preferred_countries: tuple[str, ...] = ()
    preferred_sectors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Showcase:
    position: int
    text_en: str | None
    text_de: str | None


@dataclass(frozen=True)
class CompanyRow:
    """A company with its most recent round."""
    id: str
    name: str
    country: str
    city: str | None
    sector: str | None
    size_category: str
    round_id: str
    round_date: date
    stage: str | None
    amount_eur: int | None
    amount_native: float | None
    currency: str | None
    investors: tuple[str, ...]
    description: str | None
    website: str | None
    source_url: str | None


@dataclass(frozen=True)
class PersonRow:
    name: str
    title: str
    categories: tuple[str, ...]
    level: str
    source_url: str
    read_at: date


@dataclass(frozen=True)
class EmailRow:
    address: str
    type: str
    source_url: str


@dataclass(frozen=True)
class NewMail:
    """A mail the student keeps; the store adds id, student and dates."""
    company_id: str
    round_id: str | None
    address: str
    address_type: str
    person_name: str | None
    person_key: str | None
    person_choice: str
    person_source_url: str | None
    style: str
    language: str
    company_line: str | None
    used_company_line: bool
    subject: str
    body: str
    variant: int = 0                    # mails kept before for this company and round
    size_category: str | None = None    # of the round: sets the round cap


@dataclass(frozen=True)
class Mail:
    id: str
    student_id: str | None
    company_id: str
    round_id: str | None
    address: str | None
    address_type: str | None
    person_name: str | None
    person_key: str | None
    person_choice: str
    person_source_url: str | None
    style: str
    language: str
    company_line: str | None
    used_company_line: bool
    subject: str | None
    body: str | None
    status: str
    created_at: datetime
    status_dates: dict = field(default_factory=dict)
    variant: int = 0
    size_category: str | None = None

    def record(self) -> MailRecord:
        copied = ("copied" in self.status_dates
                  or self.status in ("copied", "sent", "human_reply", "positive_reply"))
        return MailRecord(self.id, self.student_id, self.company_id, self.person_key,
                          self.status, self.created_at, round_id=self.round_id, copied=copied)


@dataclass(frozen=True)
class ListFilters:
    query: str = ""
    countries: tuple[str, ...] = ()
    sectors: tuple[str, ...] = ()
    sizes: tuple[str, ...] = ()
    months: int = 12
    page: int = 1
    with_person: bool = False


def eligible(companies: Sequence[CompanyRow], with_address: set[str], excluded: set[str],
             mails: Sequence[MailRecord], filters: ListFilters, student_id: str,
             now: datetime, with_person: set[str] = frozenset()) -> tuple[list[CompanyRow], int]:
    """The list of spec 7.2: a recent round, an address, not excluded, not
    full (unless this student wrote to it); filtered, newest round first,
    one page of 50 and the total."""
    cutoff = (now - timedelta(days=min(filters.months * 31, RECENT_ROUND_DAYS))).date()
    recent = (now - timedelta(days=RECENT_ROUND_DAYS)).date()
    own = {m.company_id for m in mails if m.student_id == student_id}
    query = filters.query.strip().lower()
    rows = []
    for c in companies:
        if c.round_date < recent or c.round_date < cutoff:
            continue
        if c.id not in with_address or c.id in excluded:
            continue
        full = rules.refusal("", c.id, None, mails, now, round_id=c.round_id,
                             size=c.size_category)
        if full and full.reason in ("company_full", "round_full") and c.id not in own:
            continue
        if query and query not in c.name.lower():
            continue
        if filters.countries and c.country not in filters.countries:
            continue
        if filters.sectors and c.sector not in filters.sectors:
            continue
        if filters.sizes and c.size_category not in filters.sizes:
            continue
        if filters.with_person and c.id not in with_person:
            continue
        rows.append(c)
    rows.sort(key=lambda c: (c.round_date, c.id), reverse=True)
    start = (max(filters.page, 1) - 1) * PAGE_SIZE
    return rows[start:start + PAGE_SIZE], len(rows)


class AppStore(Protocol):
    def invitation_code(self) -> str: ...
    def profile(self, student_id: str) -> Profile | None: ...
    def save_profile(self, profile: Profile) -> None: ...
    def showcases(self, student_id: str) -> list[Showcase]: ...
    def save_showcases(self, student_id: str, showcases: list[Showcase]) -> None: ...
    def companies(self, filters: ListFilters, student_id: str,
                  now: datetime) -> tuple[list[CompanyRow], int]: ...
    def sectors(self) -> list[str]: ...
    def company(self, company_id: str) -> CompanyRow | None: ...
    def people(self, company_id: str) -> list[PersonRow]: ...
    def emails(self, company_id: str) -> list[EmailRow]: ...
    def contact_summary(self, company_ids: Sequence[str]) -> dict[str, tuple[int, bool]]: ...
    def mail_records(self) -> list[MailRecord]: ...
    def reserve(self, student_id: str, mail: NewMail, now: datetime) -> Refusal | str: ...
    def mails(self, student_id: str) -> list[Mail]: ...
    def mail(self, student_id: str, mail_id: str) -> Mail | None: ...
    def set_status(self, student_id: str, mail_id: str, status: str, now: datetime) -> bool: ...
    def delete_student(self, student_id: str) -> None: ...


class InMemoryAppStore:
    """An AppStore in plain Python objects, for tests and `--dev`."""

    def __init__(self, invitation: str) -> None:
        self._invitation = invitation
        self._companies: dict[str, CompanyRow] = {}
        self._people: dict[str, list[PersonRow]] = {}
        self._emails: dict[str, list[EmailRow]] = {}
        self._excluded: set[str] = set()
        self._profiles: dict[str, Profile] = {}
        self._showcases: dict[str, list[Showcase]] = {}
        self._mails: list[Mail] = []
        self._lock = threading.Lock()

    # --- set-up, for tests and the seed -------------------------------------
    def add_company(self, company: CompanyRow, emails: list[EmailRow],
                    people: list[PersonRow]) -> None:
        self._companies[company.id] = company
        self._emails[company.id] = list(emails)
        self._people[company.id] = list(people)

    def exclude_company(self, company_id: str) -> None:
        self._excluded.add(company_id)

    def all_mails(self) -> list[Mail]:
        return list(self._mails)

    # --- AppStore -----------------------------------------------------------
    def invitation_code(self) -> str:
        return self._invitation

    def profile(self, student_id: str) -> Profile | None:
        return self._profiles.get(student_id)

    def save_profile(self, profile: Profile) -> None:
        self._profiles[profile.id] = profile

    def showcases(self, student_id: str) -> list[Showcase]:
        return sorted(self._showcases.get(student_id, []), key=lambda s: s.position)

    def save_showcases(self, student_id: str, showcases: list[Showcase]) -> None:
        self._showcases[student_id] = list(showcases)

    def companies(self, filters: ListFilters, student_id: str,
                  now: datetime) -> tuple[list[CompanyRow], int]:
        with_address = {cid for cid, rows in self._emails.items() if rows}
        with_person = {cid for cid, rows in self._people.items() if rows}
        return eligible(list(self._companies.values()), with_address, self._excluded,
                        self.mail_records(), filters, student_id, now, with_person)

    def sectors(self) -> list[str]:
        return sorted({c.sector for c in self._companies.values() if c.sector})

    def company(self, company_id: str) -> CompanyRow | None:
        if company_id in self._excluded or not self._emails.get(company_id):
            return None
        return self._companies.get(company_id)

    def people(self, company_id: str) -> list[PersonRow]:
        return list(self._people.get(company_id, []))

    def emails(self, company_id: str) -> list[EmailRow]:
        return list(self._emails.get(company_id, []))

    def contact_summary(self, company_ids: Sequence[str]) -> dict[str, tuple[int, bool]]:
        """For each company: how many people are named, and whether a careers
        address exists. One read for a whole page of the list."""
        return {c: (len(self.people(c)), any(e.type == "careers" for e in self.emails(c)))
                for c in company_ids}

    def mail_records(self) -> list[MailRecord]:
        return [m.record() for m in self._mails]

    def reserve(self, student_id: str, mail: NewMail, now: datetime) -> Refusal | str:
        # One lock for the whole store stands in for the per-company advisory
        # lock of reserve_mail: the check and the insert cannot interleave.
        with self._lock:
            refused = rules.refusal(student_id, mail.company_id, mail.person_key,
                                    self.mail_records(), now, round_id=mail.round_id,
                                    size=mail.size_category)
            if refused:
                return refused
            mail_id = str(uuid.uuid4())
            self._mails.append(Mail(id=mail_id, student_id=student_id, status="generated",
                                    created_at=now, **mail.__dict__))
            return mail_id

    def mails(self, student_id: str) -> list[Mail]:
        own = [m for m in self._mails if m.student_id == student_id]
        return sorted(own, key=lambda m: m.created_at, reverse=True)

    def mail(self, student_id: str, mail_id: str) -> Mail | None:
        return next((m for m in self._mails if m.id == mail_id and m.student_id == student_id),
                    None)

    def set_status(self, student_id: str, mail_id: str, status: str, now: datetime) -> bool:
        if status not in STATUSES:
            return False
        for index, m in enumerate(self._mails):
            if m.id == mail_id and m.student_id == student_id:
                dates = dict(m.status_dates)
                dates[status] = now
                self._mails[index] = replace(m, status=status, status_dates=dates)
                return True
        return False

    def delete_student(self, student_id: str) -> None:
        self._profiles.pop(student_id, None)
        self._showcases.pop(student_id, None)
        self._mails = [replace(m, student_id=None, subject=None, body=None, person_name=None,
                               person_source_url=None, address=None, company_line=None)
                       if m.student_id == student_id else m for m in self._mails]
