"""One run of the contact scraper over the companies that are due.

Everything this module returns or records is a count or a company id: the
repository is public and so are the logs of its runs.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from kaltstart.contacts.exclusions import without_excluded
from kaltstart.contacts.scrape import scrape_company
from kaltstart.contacts.store import ContactStore

REREAD_DAYS = 30            # a site that was read is read again a month later
RETRY_DAYS = 7              # an unreachable site is tried again a week later
MAX_UNREACHABLE = 3         # at the third failure in a row its rows are deleted
RECENT_ROUND_DAYS = 365     # companies without a round this recent are not kept
DEFAULT_MAX = 300           # companies per run
MAX_WRITE_ERRORS = 5        # database errors in a row that stop a run


class _TooManyWriteErrors(RuntimeError):
    pass


def next_state(outcome: str, attempts: int, now: datetime) -> tuple[int, datetime, str]:
    """`(attempts, next attempt, rows)` after a company's reading.

    `rows` says what happens to what is stored: "replace" by the new
    reading, "keep" as it is, or "delete".
    """
    if outcome != "unreachable":
        return 0, now + timedelta(days=REREAD_DAYS), "replace"
    if attempts + 1 < MAX_UNREACHABLE:
        return attempts + 1, now + timedelta(days=RETRY_DAYS), "keep"
    return 0, now + timedelta(days=REREAD_DAYS), "delete"


def _is_due(company: dict, now: datetime) -> bool:
    next_at = company["contacts_next_at"]
    return next_at is None or datetime.fromisoformat(next_at) <= now


def due_companies(candidates: list[dict], recent_ids: set[str], excluded_ids: set[str],
                  now: datetime, limit: int) -> list[dict]:
    """Eligible companies that are due: never visited first, the oldest
    company first, then the longest overdue; at most `limit`."""
    due = [c for c in candidates
           if c["id"] in recent_ids and c["id"] not in excluded_ids and _is_due(c, now)]
    never = sorted((c for c in due if c["contacts_checked_at"] is None),
                   key=lambda c: c["created_at"])
    again = sorted((c for c in due if c["contacts_checked_at"] is not None),
                   key=lambda c: datetime.fromisoformat(c["contacts_next_at"])
                   if c["contacts_next_at"] else now)
    return (never + again)[:limit]


def status(store: ContactStore, country: str, now: datetime | None = None) -> dict:
    """Counts about the companies of a country. Numbers only."""
    now = now or datetime.now(timezone.utc)
    excluded_ids = {row["company_id"] for row in store.exclusions()
                    if row["person_key"] is None}
    recent_ids = store.company_ids_with_round_since(
        (now - timedelta(days=RECENT_ROUND_DAYS)).date())
    candidates = store.candidate_companies(country)
    eligible = [c for c in candidates
                if c["id"] in recent_ids and c["id"] not in excluded_ids]
    visited = [c for c in eligible if c["contacts_checked_at"] is not None]
    with_people = store.company_ids_with_people()
    return {
        "eligible": len(eligible),
        "visited": len(visited),
        "with_address": sum(1 for c in visited if c["contacts_outcome"] == "ok"),
        "with_people": sum(1 for c in eligible if c["id"] in with_people),
        "due_now": len(due_companies(candidates, recent_ids, excluded_ids, now,
                                     limit=len(candidates))),
        "outcomes": dict(Counter(c["contacts_outcome"] for c in visited)),
    }


def _rows(company_id: str, emails, people, read_at: str) -> tuple[list[dict], list[dict]]:
    email_rows = [{"company_id": company_id, "address": e.address, "type": e.type,
                   "source_url": e.source_url, "read_at": read_at} for e in emails]
    people_rows = [{"company_id": company_id, "name": p.name, "title": p.title,
                    "categories": list(p.categories), "level": p.level,
                    "source_url": p.source_url, "read_at": read_at} for p in people]
    return email_rows, people_rows


def run(store: ContactStore, fetcher, *, country: str = "Switzerland",
        limit: int = DEFAULT_MAX, now: datetime | None = None) -> dict:
    """Read the due companies and store what was found. Returns the run row,
    which is also recorded in the store, whether the run succeeds or fails."""
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat()
    outcomes: Counter[str] = Counter()
    summary = {"started_at": stamp, "finished_at": stamp, "status": "success",
               "country": country, "companies_visited": 0, "with_address": 0,
               "with_people": 0, "outcomes": {}, "error": None}
    try:
        exclusions = store.exclusions()
        excluded_ids = {row["company_id"] for row in exclusions if row["person_key"] is None}
        person_keys = frozenset(row["person_key"] for row in exclusions if row["person_key"])
        recent_ids = store.company_ids_with_round_since(
            (now - timedelta(days=RECENT_ROUND_DAYS)).date())
        stored = store.company_ids_with_contacts()
        stale = sorted(stored - (recent_ids - excluded_ids))
        if stale:
            store.delete_contacts(stale)

        write_errors = 0
        for company in due_companies(store.candidate_companies(country), recent_ids,
                                     excluded_ids, now, limit):
            company_id = company["id"]
            # The size only drives the proposed contact, which is not stored.
            result = scrape_company(
                {"company_id": company_id, "name": company["name"],
                 "website": company["website"], "size_category": "small"}, fetcher)
            emails, people = without_excluded(result, person_keys)
            outcome = "ok" if emails else (result.failure or "no_address")
            attempts, next_at, rows = next_state(outcome, company["contacts_attempts"], now)
            try:
                if rows == "replace":
                    store.replace_contacts(company_id, *_rows(company_id, emails, people, stamp))
                elif rows == "delete":
                    store.delete_contacts([company_id])
                store.set_contact_state(company_id, checked_at=stamp, outcome=outcome,
                                        attempts=attempts, next_at=next_at.isoformat())
            except Exception as exc:
                # The company's state is untouched: it is due again next run.
                write_errors += 1
                if write_errors >= MAX_WRITE_ERRORS:
                    raise _TooManyWriteErrors(type(exc).__name__) from None
                continue
            write_errors = 0
            outcomes[outcome] += 1
            summary["companies_visited"] += 1
            summary["with_address"] += outcome == "ok"
            summary["with_people"] += bool(people) and rows == "replace"
    except _TooManyWriteErrors as exc:
        summary.update(status="failed", error=str(exc))
    except Exception as exc:
        # The class name only: a message may quote a row, and logs are public.
        summary.update(status="failed", error=type(exc).__name__)
    summary["outcomes"] = dict(outcomes)
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    store.record_contact_run(summary)
    return summary
