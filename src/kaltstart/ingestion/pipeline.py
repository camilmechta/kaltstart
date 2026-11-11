"""Ingestion pipelines: backfill, incremental sync, details fetch, reclean.

Each pipeline returns a run dict (the shape of a `sync_runs` row, minus `id`)
and records it with `store.record_run`, also when it fails.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from kaltstart.ingestion.store import Store
from kaltstart.ingestion.techeu_client import BudgetExhaustedError, TechEuClient, TechEuError
from kaltstart.ingestion.transform import transform_company_details, transform_round

COUNTRIES = ("Switzerland", "Germany", "Austria")
MAX_CONSECUTIVE_DETAIL_FAILURES = 3


@contextmanager
def _recorded_run(store: Store, command: str,
                  client: TechEuClient | None = None) -> Iterator[dict]:
    """Yield a run dict to fill in; record it as success or failed on exit."""
    requests_at_start = client.requests_made if client else 0
    run = {
        "command": command,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "success",
        "rounds_upserted": 0,
        "rounds_removed": 0,
        "companies_upserted": 0,
        "details_fetched": 0,
        "requests_made": 0,
        "error": None,
    }
    try:
        yield run
    except BaseException as exc:
        run["status"] = "failed"
        run["error"] = str(exc) or type(exc).__name__
        raise
    finally:
        run["finished_at"] = datetime.now(timezone.utc).isoformat()
        if client:
            run["requests_made"] = client.requests_made - requests_at_start
        store.record_run(run)


def _store_rounds(store: Store, raws: list[dict]) -> tuple[int, int]:
    """Write raw rounds, then companies, then rounds.

    Returns (companies_upserted, rounds_upserted). Each company row comes from
    its latest round in the batch; on equal dates the later one wins.
    """
    store.upsert_raw_rounds(raws)
    rounds = {}
    companies = {}
    # Sorted by date (stable), so the last one seen per company is its latest.
    for raw in sorted(raws, key=lambda r: r["date"]):
        company, rnd = transform_round(raw)
        companies[company["id"]] = company
        rounds[rnd["id"]] = rnd
    store.upsert_companies(list(companies.values()))
    store.upsert_rounds(list(rounds.values()))
    return len(companies), len(rounds)


def backfill(client: TechEuClient, store: Store, date_from: str,
             date_to: str) -> dict:
    with _recorded_run(store, "backfill", client) as run:
        for country in COUNTRIES:
            raws = list(client.iter_rounds(country, date_from, date_to))
            companies, rounds = _store_rounds(store, raws)
            run["companies_upserted"] += companies
            run["rounds_upserted"] += rounds
    return run


def sync_changes(client: TechEuClient, store: Store) -> dict:
    with _recorded_run(store, "sync", client) as run:
        last = store.last_successful_run_started_at()
        if last is None:
            raise RuntimeError("no successful run found: run backfill first")
        since = (datetime.fromisoformat(last) - timedelta(days=1)).isoformat()
        added, removed = client.fetch_changes(since)
        ours = [r for r in added if r["company"]["country"] in COUNTRIES]
        run["rounds_removed"] = store.delete_rounds(removed)
        companies, rounds = _store_rounds(store, ours)
        run["companies_upserted"] = companies
        run["rounds_upserted"] = rounds
    return run


def fetch_company_details(client: TechEuClient, store: Store,
                          limit: int = 1000) -> dict:
    with _recorded_run(store, "details", client) as run:
        failures = 0
        consecutive = 0
        for company_id in store.company_ids_missing_details(limit):
            try:
                raw = client.get_company(company_id)
                store.set_company_details(
                    company_id, transform_company_details(raw))
            except BudgetExhaustedError:
                break
            except Exception as exc:
                failures += 1
                consecutive += 1
                if consecutive >= MAX_CONSECUTIVE_DETAIL_FAILURES:
                    raise TechEuError(
                        f"details fetch stopped after "
                        f"{MAX_CONSECUTIVE_DETAIL_FAILURES} consecutive "
                        f"failures: {exc}") from exc
                continue
            consecutive = 0
            run["details_fetched"] += 1
        if failures:
            run["error"] = f"details failed for {failures} companies"
    return run


def reclean(store: Store) -> dict:
    with _recorded_run(store, "reclean") as run:
        companies, rounds = _store_rounds(store, store.all_raw_rounds())
        run["companies_upserted"] = companies
        run["rounds_upserted"] = rounds
    return run
