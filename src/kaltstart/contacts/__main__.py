"""Command line: python -m kaltstart.contacts <command>."""

import argparse
import csv
import sys
from pathlib import Path

from kaltstart.contacts.fetcher import SiteFetcher, default_http_client
from kaltstart.contacts.measurement import (
    check_problems, read_results, reported_rates, summarise, write_results)
from kaltstart.contacts.scrape import scrape_company
from kaltstart.contacts.site import site_host


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m kaltstart.contacts")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("measure", help="scrape the companies of a sample file")
    p.add_argument("sample", type=Path)
    p.add_argument("--out", type=Path, default=Path("local/phase-2-results.csv"))
    p = sub.add_parser("summary", help="summarise verified results")
    p.add_argument("results", type=Path)
    p.add_argument("--out", type=Path,
                   default=Path("docs/measurements/phase-2-summary.md"))
    return parser


def _measure(sample: Path, out: Path, fetcher) -> None:
    with sample.open(newline="", encoding="utf-8") as handle:
        companies = list(csv.DictReader(handle))
    if fetcher is None:
        fetcher = SiteFetcher(default_http_client())
    results = []
    for number, company in enumerate(companies, start=1):
        result = scrape_company(company, fetcher)
        results.append(result)
        print(f"{number}/{len(companies)} {site_host(company['website'])}: "
              f"{result.failure or 'ok'}", flush=True)
    write_results(results, out)
    contacts, founders = reported_rates(read_results(out))
    print(f"Usable contact (reported): {contacts}")
    print(f"Founder name (reported): {founders}")
    print(f"Results written to {out}")


def _summary(results: Path, out: Path) -> None:
    rows = read_results(results)
    problems = check_problems(rows)
    if problems:
        raise RuntimeError("results are not fully verified:\n  " + "\n  ".join(problems))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(summarise(rows), encoding="utf-8")
    print(f"Summary written to {out}")


def main(argv: list[str], *, fetcher=None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        if args.command == "measure":
            _measure(args.sample, args.out, fetcher)
        else:
            _summary(args.results, args.out)
    except (RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
