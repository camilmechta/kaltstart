"""Reservation and tracking rules (spec 7.1 and parent 7.4), as pure
functions. The SQL function reserve_mail (migration 0004) applies the same
rules inside one transaction; these serve the in-memory store, the early
check of a preview, and the pages."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

COMPANY_CAP = 3
CAP_DAYS = 30
PENDING_LIMIT = 5
PRESUMED_SENT_DAYS = 7
REMINDER_HOURS = 72
_PENDING = ("generated", "copied")


@dataclass(frozen=True)
class MailRecord:
    id: str
    student_id: str | None          # None once the student deleted their account
    company_id: str
    person_key: str | None
    status: str
    created_at: datetime


@dataclass(frozen=True)
class Refusal:
    reason: str                     # company_full, student_pending, company_done, person_done
    frees_on: date | None


def _age(mail: MailRecord, now: datetime) -> timedelta:
    return now - mail.created_at


def shown_status(mail: MailRecord, now: datetime) -> str:
    if mail.status in _PENDING and _age(mail, now) >= timedelta(days=PRESUMED_SENT_DAYS):
        return "presumed_sent"
    return mail.status


def _counting(company_id: str, mails: Sequence[MailRecord], now: datetime) -> list[MailRecord]:
    return [m for m in mails if m.company_id == company_id and m.status != "abandoned"
            and _age(m, now) < timedelta(days=CAP_DAYS)]


def pending_count(student_id: str, mails: Sequence[MailRecord], now: datetime) -> int:
    return sum(1 for m in mails if m.student_id == student_id
               and shown_status(m, now) in _PENDING)


def refusal(student_id: str, company_id: str, person_key: str | None,
            mails: Sequence[MailRecord], now: datetime) -> Refusal | None:
    counting = _counting(company_id, mails, now)
    if len(counting) >= COMPANY_CAP:
        oldest = min(m.created_at for m in counting)
        return Refusal("company_full", (oldest + timedelta(days=CAP_DAYS)).date())
    if pending_count(student_id, mails, now) >= PENDING_LIMIT:
        return Refusal("student_pending", None)
    own = [m for m in mails if m.student_id == student_id and m.status != "abandoned"]
    if any(m.company_id == company_id for m in own):
        return Refusal("company_done", None)
    if person_key and any(m.person_key == person_key for m in own):
        return Refusal("person_done", None)
    return None


def needs_reminder(mail: MailRecord, now: datetime) -> bool:
    age = _age(mail, now)
    return (mail.status in _PENDING and timedelta(hours=REMINDER_HOURS) <= age
            < timedelta(days=PRESUMED_SENT_DAYS))


def last_slot(company_id: str, mails: Sequence[MailRecord], now: datetime) -> bool:
    return len(_counting(company_id, mails, now)) == COMPANY_CAP - 1
