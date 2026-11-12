"""Command line: python -m kaltstart.ingestion <command>."""

import argparse
import calendar
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date

import httpx

from kaltstart.ingestion.pipeline import (
    backfill,
    fetch_company_details,
    reclean,
    sync_changes,
)
from kaltstart.ingestion.store import Store
from kaltstart.ingestion.techeu_client import BASE_URL, TechEuClient, TechEuError

SIZE_ORDER = ("small", "medium", "large")
NONE_LABEL = "(none)"


def _today() -> date:
    return date.today()


def months_back(today: date, months: int) -> date:
    """The same day `months` calendar months earlier, clamped to month length."""
    index = today.year * 12 + (today.month - 1) - months
    year, month = divmod(index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _default_client() -> TechEuClient:
    return TechEuClient(httpx.Client(base_url=BASE_URL, timeout=30))


def _default_store() -> Store:
    from kaltstart.ingestion.supabase_store import SupabaseStore

    return SupabaseStore.from_env()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m kaltstart.ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("backfill", help="load rounds for a period, then company details")
    p.add_argument("--months", type=int, default=12)
    sub.add_parser("sync", help="apply changes since the last run, then company details")
    sub.add_parser("reclean", help="rebuild companies and rounds from stored raw rounds")
    sub.add_parser("report", help="print counts and breakdowns (no API calls)")
    sub.add_parser("cities", help="print distinct cities and raw city spellings")
    return parser


def _print_run(run: dict) -> None:
    for key, value in run.items():
        print(f"{key}: {value}")


def _label(value) -> str:
    return NONE_LABEL if value is None else str(value)


def _table(header: list[str], rows: list[list[str]]) -> None:
    table = [header] + rows
    widths = [max(len(r[i]) for r in table) for i in range(len(header))]
    for row in table:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip())


def _report(store: Store) -> None:
    for key, value in store.counts().items():
        print(f"{key}: {value}")
    items = store.all_rounds_with_company()

    companies = {i["company"]["id"]: i["company"] for i in items}
    total = len(companies)
    for label, key in (("companies_with_details", "details_fetched_at"),
                       ("companies_with_website", "website")):
        n = sum(1 for c in companies.values() if c.get(key))
        share = f" ({n / total:.0%})" if total else ""
        print(f"{label}: {n} of {total}{share}")

    print("\nRounds per country")
    per_country = Counter(_label(i["company"]["country"]) for i in items)
    _table(["country", "rounds"],
           [[c, str(n)] for c, n in sorted(per_country.items())])

    print("\nStage x size category (rounds)")
    stages = sorted({_label(i["stage"]) for i in items})
    sizes = {_label(i["size_category"]) for i in items}
    size_rows = [s for s in SIZE_ORDER if s in sizes] + sorted(sizes - set(SIZE_ORDER))
    cells = Counter((_label(i["size_category"]), _label(i["stage"])) for i in items)
    _table(["size_category"] + stages,
           [[s] + [str(cells[(s, st)]) for st in stages] for s in size_rows])

    print("\nMedian amount_eur by stage (known stages only)")
    amounts = defaultdict(list)
    known = set()
    for i in items:
        if i["stage"] in (None, "Other"):
            continue
        known.add(i["stage"])
        if i["amount_eur"] is not None:
            amounts[i["stage"]].append(i["amount_eur"])
    rows = []
    for stage in sorted(known):
        values = amounts[stage]
        median = f"{statistics.median(values):,.0f}" if values else "-"
        rows.append([stage, f"n={len(values)}", median])
    _table(["stage", "rounds_with_amount", "median"], rows)


def _cities(store: Store) -> None:
    companies = {}
    for item in store.all_rounds_with_company():
        companies[item["company"]["id"]] = item["company"]
    counts = Counter((_label(c["country"]), _label(c["city"])) for c in companies.values())
    ordered = sorted(counts.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1]))
    _table(["country", "city", "companies"],
           [[country, city, str(n)] for (country, city), n in ordered])

    print("\nCity values that differ from the raw spelling")
    pairs = Counter((_label(c["country"]), c["city_raw"], c["city"])
                    for c in companies.values() if c["city_raw"] != c["city"])
    _table(["country", "city_raw", "city", "companies"],
           [[country, repr(raw), _label(city), str(n)]
            for (country, raw, city), n in sorted(
                pairs.items(), key=lambda kv: tuple(map(str, kv[0])))])


def _run_command(args: argparse.Namespace, client, store) -> None:
    command = args.command
    if store is None:
        store = _default_store()
    if command in ("report", "cities", "reclean"):
        if command == "report":
            _report(store)
        elif command == "cities":
            _cities(store)
        else:
            _print_run(reclean(store))
        return
    if client is None:
        client = _default_client()
    if command == "backfill":
        today = _today()
        run = backfill(client, store, months_back(today, args.months).isoformat(),
                       today.isoformat())
    else:
        run = sync_changes(client, store)
    _print_run(run)
    _print_run(fetch_company_details(client, store))


def main(argv: list[str], *, client=None, store=None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        _run_command(args, client, store)
    except (RuntimeError, TechEuError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
