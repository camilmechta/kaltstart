"""Results file, rates, verdict and summary of a measurement."""

import csv
from collections import Counter
from pathlib import Path
from typing import Sequence

from kaltstart.contacts.models import CompanyResult
from kaltstart.contacts.scrape import FAILURES

RESULT_COLUMNS = (
    "company_id", "name", "website", "size_category", "pages_fetched", "emails",
    "founders", "contact_address", "contact_founder", "confidence", "failure",
    "email_check", "founder_check", "notes")
# confirmed: the scraper's find is right. wrong: it reported something false.
# missed: the site publishes one and the scraper found none.
# none_exists: nothing to find and nothing reported.
CHECK_VALUES = ("confirmed", "wrong", "missed", "none_exists")
CONTACT_THRESHOLD = 0.65    # lowered from 0.70 on 2026-11-12, decision D39
FOUNDER_THRESHOLD = 0.4
_SIZES = ("small", "medium", "large")
_CONFIDENCES = ("high", "medium", "low")


def _row(result: CompanyResult) -> dict:
    contact = result.contact
    return {
        "company_id": result.company_id, "name": result.name,
        "website": result.website, "size_category": result.size_category,
        "pages_fetched": len(result.pages_fetched),
        "emails": " ; ".join(f"{e.address}|{e.type}|{e.source_url}" for e in result.emails),
        "founders": " ; ".join(f"{f.name}|{f.role}|{f.source_url}" for f in result.founders),
        "contact_address": contact.address if contact else "",
        "contact_founder": (contact.founder_name or "") if contact else "",
        "confidence": contact.confidence if contact else "",
        "failure": result.failure or "",
        "email_check": "", "founder_check": "", "notes": "",
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
    problems = []
    for row in rows:
        for column, reported in (("email_check", bool(row["emails"])),
                                 ("founder_check", bool(row["founders"]))):
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
            _rate(sum(1 for r in rows if r["founders"]), n))


def summarise(rows: Sequence[dict]) -> str:
    """Markdown summary. Contains no company, website, address or person."""
    n = len(rows)
    contacts, founders = reported_rates(rows)
    checks = {column: Counter(r[column] for r in rows)
              for column in ("email_check", "founder_check")}
    confirmed_contacts = checks["email_check"]["confirmed"]
    confirmed_founders = checks["founder_check"]["confirmed"]
    causes = Counter(r["failure"] for r in rows if r["failure"])
    lines = [
        "# Phase 2 measurement", "",
        f"Companies: {n}", "",
        "## Rates", "",
        f"- Usable contact: reported {contacts}, confirmed {_rate(confirmed_contacts, n)}",
        f"- Founder name: reported {founders}, confirmed {_rate(confirmed_founders, n)}",
        "", "## Scraper mistakes found by the verification", "",
        f"- wrong address: {checks['email_check']['wrong']}",
        f"- missed address: {checks['email_check']['missed']}",
        f"- wrong founder name: {checks['founder_check']['wrong']}",
        f"- missed founder name: {checks['founder_check']['missed']}",
        "", "## Failure causes (companies without a usable contact)", "",
    ]
    lines += [f"- {cause}: {causes[cause]}" for cause in FAILURES]
    lines += ["", "## Proposed contacts by confidence and size category", "",
              "| size | high | medium | low | none |", "|---|---|---|---|---|"]
    for size in _SIZES:
        of_size = [r for r in rows if r["size_category"] == size]
        cells = [sum(1 for r in of_size if r["confidence"] == c) for c in _CONFIDENCES]
        cells.append(sum(1 for r in of_size if not r["confidence"]))
        lines.append(f"| {size} | " + " | ".join(str(c) for c in cells) + " |")
    lines += [
        "", "## Verdict", "",
        "Counted on confirmed results. Within one company of a threshold, the "
        "result is inconclusive.", "",
        f"- Usable contact (threshold {CONTACT_THRESHOLD:.0%}): "
        f"{verdict(confirmed_contacts, n, CONTACT_THRESHOLD)}",
        f"- Founder name (threshold {FOUNDER_THRESHOLD:.0%}): "
        f"{verdict(confirmed_founders, n, FOUNDER_THRESHOLD)}",
        "",
    ]
    return "\n".join(lines)
