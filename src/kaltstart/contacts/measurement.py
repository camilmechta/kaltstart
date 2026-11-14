"""Results file, rates, verdict and summary of a measurement."""

import csv
from collections import Counter
from pathlib import Path
from typing import Sequence

from kaltstart.contacts.models import CompanyResult
from kaltstart.contacts.scrape import FAILURES
from kaltstart.contacts.titles import CATEGORIES

RESULT_COLUMNS = (
    "company_id", "name", "website", "size_category", "pages_fetched", "emails",
    "people", "contact_address", "contact_person", "confidence", "failure",
    "email_check", "people_check", "notes")
# For both checks. confirmed: everything the scraper reported is right.
# wrong: at least one thing it reported is false.
# missed: the site publishes one and the scraper found none.
# none_exists: nothing to find and nothing reported.
CHECK_VALUES = ("confirmed", "wrong", "missed", "none_exists")
CONTACT_THRESHOLD = 0.65     # lowered from 0.70 on 2026-11-12, decision D39
ACCURACY_THRESHOLD = 0.9     # share of reported people lists that are right; blocking
COVERAGE_THRESHOLD = 0.4     # share of companies with a right list; a goal
_SIZES = ("small", "medium", "large")
_CONFIDENCES = ("high", "medium", "low")


def _row(result: CompanyResult) -> dict:
    contact = result.contact
    return {
        "company_id": result.company_id, "name": result.name,
        "website": result.website, "size_category": result.size_category,
        "pages_fetched": len(result.pages_fetched),
        "emails": " ; ".join(f"{e.address}|{e.type}|{e.source_url}" for e in result.emails),
        "people": " ; ".join(
            f"{p.name}|{p.title}|{'+'.join(p.categories)}|{p.level}|{p.source_url}"
            for p in result.people),
        "contact_address": contact.address if contact else "",
        "contact_person": (contact.person_name or "") if contact else "",
        "confidence": contact.confidence if contact else "",
        "failure": result.failure or "",
        "email_check": "", "people_check": "", "notes": "",
    }


def write_results(results: Sequence[CompanyResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(_row(result) for result in results)


def read_results(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verdict(count: int, n: int, threshold: float) -> str:
    """`inconclusive` within one company of the threshold, else pass or fail."""
    target = threshold * n
    if abs(count - target) <= 1:
        return "inconclusive"
    return "pass" if count > target else "fail"


def check_problems(rows: Sequence[dict]) -> list[str]:
    """One message per row whose verification is missing or inconsistent."""
    missing = [column for column in ("people", "people_check")
               if rows and column not in rows[0]]
    if missing:
        return [f"this results file has no {' or '.join(missing)} column: it was "
                f"written before the scraper read people; run measure again"]
    problems = []
    for row in rows:
        for column, reported in (("email_check", bool(row["emails"])),
                                 ("people_check", bool(row["people"]))):
            value = row[column]
            allowed = ("confirmed", "wrong") if reported else ("missed", "none_exists")
            if value not in CHECK_VALUES:
                problems.append(f"{row['company_id']}: {column} is {value!r}, "
                                f"expected one of {', '.join(CHECK_VALUES)}")
                break
            if value not in allowed:
                problems.append(f"{row['company_id']}: {column} is {value!r} but the "
                                f"scraper reported {'a find' if reported else 'nothing'}")
                break
    return problems


def _rate(count: int, n: int) -> str:
    return f"{count}/{n} ({count / n:.0%})" if n else "0/0"


def reported_rates(rows: Sequence[dict]) -> tuple[str, str]:
    n = len(rows)
    return (_rate(sum(1 for r in rows if r["emails"]), n),
            _rate(sum(1 for r in rows if r["people"]), n))


def _categories(row: dict) -> set[str]:
    return {category for entry in row["people"].split(" ; ") if entry
            for category in entry.split("|")[2].split("+")}


def summarise(rows: Sequence[dict]) -> str:
    """Markdown summary. Contains no company, website, address or person."""
    n = len(rows)
    contacts, _people = reported_rates(rows)
    checks = {column: Counter(r[column] for r in rows)
              for column in ("email_check", "people_check")}
    confirmed_contacts = checks["email_check"]["confirmed"]
    right = checks["people_check"]["confirmed"]
    wrong = checks["people_check"]["wrong"]
    lists = right + wrong
    accuracy = (f"{right}/{lists} lists right ({right / lists:.0%})" if lists
                else "0/0 lists right")
    accuracy_verdict = verdict(right, lists, ACCURACY_THRESHOLD) if lists else "fail"
    causes = Counter(r["failure"] for r in rows if r["failure"])
    with_category = Counter(category for r in rows for category in _categories(r))
    lines = [
        "# Phase 2 measurement", "",
        f"Companies: {n}", "",
        "## Rates", "",
        f"- Usable contact: reported {contacts}, confirmed {_rate(confirmed_contacts, n)}",
        f"- People, accuracy: {accuracy}",
        f"- People, coverage: {_rate(right, n)}",
        "", "## Scraper mistakes found by the verification", "",
        f"- wrong address: {checks['email_check']['wrong']}",
        f"- missed address: {checks['email_check']['missed']}",
        f"- wrong people list: {wrong}",
        f"- missed people: {checks['people_check']['missed']}",
        "", "## Failure causes (companies without a usable contact)", "",
    ]
    lines += [f"- {cause}: {causes[cause]}" for cause in FAILURES]
    lines += ["", "## Companies with a person reported, by category", ""]
    lines += [f"- {category}: {with_category[category]}" for category in CATEGORIES]
    lines += ["", "## Proposed contacts by confidence and size category", "",
              "| size | high | medium | low | none |", "|---|---|---|---|---|"]
    for size in _SIZES:
        of_size = [r for r in rows if r["size_category"] == size]
        cells = [sum(1 for r in of_size if r["confidence"] == c) for c in _CONFIDENCES]
        cells.append(sum(1 for r in of_size if not r["confidence"]))
        lines.append(f"| {size} | " + " | ".join(str(c) for c in cells) + " |")
    lines += [
        "", "## Verdict", "",
        "Counted on confirmed results. Within one company (or one list, for "
        "accuracy) of a threshold, the result is inconclusive.", "",
        f"- Usable contact (threshold {CONTACT_THRESHOLD:.0%}): "
        f"{verdict(confirmed_contacts, n, CONTACT_THRESHOLD)}",
        f"- People accuracy (threshold {ACCURACY_THRESHOLD:.0%}, blocking): "
        f"{accuracy_verdict}",
        f"- People coverage (threshold {COVERAGE_THRESHOLD:.0%}, goal): "
        f"{verdict(right, n, COVERAGE_THRESHOLD)}",
        "",
    ]
    return "\n".join(lines)
