"""Storage interface for ingested data, with an in-memory implementation."""

import copy
from datetime import datetime, timezone
from typing import Protocol

from kaltstart.ingestion.transform import CompanyDetails, CompanyRow, RoundRow

WATERMARK_COMMANDS = ("backfill", "sync")


class Store(Protocol):
    def upsert_raw_rounds(self, raws: list[dict]) -> None: ...

    def upsert_companies(self, rows: list[CompanyRow]) -> None: ...

    def upsert_rounds(self, rows: list[RoundRow]) -> None: ...

    def delete_rounds(self, ids: list[str]) -> int: ...

    def all_raw_rounds(self) -> list[dict]: ...

    def company_ids_missing_details(self, limit: int) -> list[str]: ...

    def set_company_details(
        self, company_id: str, details: CompanyDetails
    ) -> None: ...

    def last_successful_run_started_at(self) -> str | None:
        """Latest started_at among successful runs of WATERMARK_COMMANDS."""
        ...

    def record_run(self, run: dict) -> None: ...

    def counts(self) -> dict[str, int]: ...

    def all_rounds_with_company(self) -> list[dict]: ...


class InMemoryStore:
    """Dict-backed Store. Copies everything in and out to avoid aliasing."""

    def __init__(self) -> None:
        self._raw_rounds: dict[str, dict] = {}
        self._companies: dict[str, dict] = {}
        self._rounds: dict[str, dict] = {}
        self._runs: list[dict] = []

    def upsert_raw_rounds(self, raws: list[dict]) -> None:
        for raw in raws:
            self._raw_rounds[raw["id"]] = copy.deepcopy(raw)

    def upsert_companies(self, rows: list[CompanyRow]) -> None:
        for row in rows:
            existing = self._companies.get(row["id"])
            merged = copy.deepcopy(dict(row))
            if existing is None:
                merged.update(
                    website=None,
                    description=None,
                    founded=None,
                    details_fetched_at=None,
                )
            else:
                for key in ("website", "description", "founded", "details_fetched_at"):
                    merged[key] = existing[key]
            self._companies[row["id"]] = merged

    def upsert_rounds(self, rows: list[RoundRow]) -> None:
        for row in rows:
            self._rounds[row["id"]] = copy.deepcopy(dict(row))

    def delete_rounds(self, ids: list[str]) -> int:
        deleted = 0
        for round_id in ids:
            if self._rounds.pop(round_id, None) is not None:
                deleted += 1
            self._raw_rounds.pop(round_id, None)
        return deleted

    def all_raw_rounds(self) -> list[dict]:
        return [copy.deepcopy(raw) for raw in self._raw_rounds.values()]

    def company_ids_missing_details(self, limit: int) -> list[str]:
        missing = [
            cid
            for cid, row in self._companies.items()
            if row["details_fetched_at"] is None
        ]
        return missing[:limit]

    def set_company_details(self, company_id: str, details: CompanyDetails) -> None:
        row = self._companies[company_id]
        row["website"] = details["website"]
        row["description"] = details["description"]
        row["founded"] = details["founded"]
        row["details_fetched_at"] = datetime.now(timezone.utc).isoformat()

    def last_successful_run_started_at(self) -> str | None:
        started = [
            r["started_at"]
            for r in self._runs
            if r["status"] == "success" and r["command"] in WATERMARK_COMMANDS
        ]
        return max(started) if started else None

    def record_run(self, run: dict) -> None:
        self._runs.append(copy.deepcopy(run))

    def counts(self) -> dict[str, int]:
        return {
            "raw_rounds": len(self._raw_rounds),
            "companies": len(self._companies),
            "rounds": len(self._rounds),
        }

    def all_rounds_with_company(self) -> list[dict]:
        return [
            {**copy.deepcopy(row), "company": copy.deepcopy(self._companies[row["company_id"]])}
            for row in self._rounds.values()
        ]
