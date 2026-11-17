"""Reservation and tracking rules (spec 7.1 and parent 7.4), as pure
functions. The SQL function reserve_mail (migration 0004) applies the same
rules inside one transaction; these serve the in-memory store, the early
check of a preview, and the pages."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Sequence

COMPANY_CAP = 3
CAP_DAYS = 30
PENDING_LIMIT = 5
PRESUMED_SENT_DAYS = 7
REMINDER_HOURS = 72
_PENDING = ("generated", "copied")


@dataclass(frozen=True)
class Limits:
    """Every sending limit in one place. The server passes them to the SQL
    function reserve_mail, so changing a value here is enough (no migration)."""
    company_cap: int = COMPANY_CAP          # kept mails per company ...
    cap_days: int = CAP_DAYS                # ... in this many rolling days
    round_cap: dict = field(default_factory=lambda: {"small": 6, "medium": 9, "large": 15})
    speed: int = 10                         # kept mails per student ...
    speed_days: int = 7                     # ... in this many rolling days
    pending: int = PENDING_LIMIT            # mails in progress per student

    def as_json(self) -> dict:
        return {"company_cap": self.company_cap, "cap_days": self.cap_days,
                "round_cap": dict(self.round_cap), "speed": self.speed,
                "speed_days": self.speed_days, "pending": self.pending}


LIMITS = Limits()


@dataclass(frozen=True)
class MailRecord:
    id: str
    student_id: str | None          # None once the student deleted their account
    company_id: str
    person_key: str | None
    status: str
    created_at: datetime
    round_id: str | None = None
    copied: bool = False            # the text was copied once: it may have been sent


@dataclass(frozen=True)
class Refusal:
    # company_full, round_full, student_speed, student_pending, company_done, person_done
    reason: str
    frees_on: date | None


def _age(mail: MailRecord, now: datetime) -> timedelta:
    return now - mail.created_at


def shown_status(mail: MailRecord, now: datetime) -> str:
    if mail.status in _PENDING and _age(mail, now) >= timedelta(days=PRESUMED_SENT_DAYS):
        return "presumed_sent"
    return mail.status


def _holds_a_slot(m: MailRecord) -> bool:
    """An abandoned mail frees its slot only if its text was never copied."""
    return m.status != "abandoned" or m.copied


def _counting(company_id: str, mails: Sequence[MailRecord], now: datetime) -> list[MailRecord]:
    return [m for m in mails if m.company_id == company_id and _holds_a_slot(m)
            and _age(m, now) < timedelta(days=LIMITS.cap_days)]


def _in_round(company_id: str, round_id: str | None, mails: Sequence[MailRecord]) -> list[MailRecord]:
    return [m for m in mails if m.company_id == company_id and round_id is not None
            and m.round_id == round_id and _holds_a_slot(m)]


def _round_cap(size: str | None) -> int | None:
    return LIMITS.round_cap.get(size) if size else None


def pending_count(student_id: str, mails: Sequence[MailRecord], now: datetime) -> int:
    return sum(1 for m in mails if m.student_id == student_id
               and shown_status(m, now) in _PENDING)


def refusal(student_id: str, company_id: str, person_key: str | None,
            mails: Sequence[MailRecord], now: datetime, *, round_id: str | None = None,
            size: str | None = None) -> Refusal | None:
    counting = _counting(company_id, mails, now)
    if len(counting) >= LIMITS.company_cap:
        oldest = min(m.created_at for m in counting)
        return Refusal("company_full", (oldest + timedelta(days=LIMITS.cap_days)).date())
    cap = _round_cap(size)
    if cap is not None and len(_in_round(company_id, round_id, mails)) >= cap:
        return Refusal("round_full", None)
    recent = sorted(m.created_at for m in mails if m.student_id == student_id
                    and _age(m, now) < timedelta(days=LIMITS.speed_days))
    if student_id and len(recent) >= LIMITS.speed:
        return Refusal("student_speed", (recent[0] + timedelta(days=LIMITS.speed_days)).date())
    if pending_count(student_id, mails, now) >= LIMITS.pending:
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


def places_left(company_id: str, round_id: str | None, size: str | None,
                mails: Sequence[MailRecord], now: datetime) -> int:
    left = LIMITS.company_cap - len(_counting(company_id, mails, now))
    cap = _round_cap(size)
    if cap is not None:
        left = min(left, cap - len(_in_round(company_id, round_id, mails)))
    return max(left, 0)


def variant_for(company_id: str, round_id: str | None, mails: Sequence[MailRecord]) -> int:
    """How many mails were ever kept for this company and round, abandoned ones
    included: the next mail takes the next wording (generator variant)."""
    return sum(1 for m in mails if m.company_id == company_id and m.round_id == round_id)
