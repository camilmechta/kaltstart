"""Supabase-backed Store (service-role key, used by the ingestion scripts)."""

import os
from datetime import datetime, timezone
from typing import Any, Iterator

from supabase import Client, create_client

from kaltstart.ingestion.store import WATERMARK_COMMANDS
from kaltstart.ingestion.transform import CompanyDetails, CompanyRow, RoundRow

WRITE_BATCH = 500
DELETE_BATCH = 100  # ids are 36-character UUIDs, and they go into the URL
PAGE_SIZE = 1000


def _batches(rows: list, size: int = WRITE_BATCH) -> Iterator[list]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def dedupe_by_id(rows: list[dict]) -> list[dict]:
    """Keep one row per id: the last one wins, ids stay in first-seen order.

    Postgres rejects an upsert that touches the same row twice in one statement.
    """
    return list({row["id"]: row for row in rows}.values())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseStore:
    def __init__(self, client: Client) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "SupabaseStore":
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        return cls(create_client(url, key))

    def _upsert(self, table: str, rows: list[dict]) -> None:
        for batch in _batches(dedupe_by_id(rows)):
            self._client.table(table).upsert(batch).execute()

    def _read_all(self, table: str, columns: str = "*") -> list[dict]:
        """Read every row of a table, paging past the 1000-row response cap."""
        out: list[dict] = []
        start = 0
        while True:
            page = (
                self._client.table(table)
                .select(columns)
                .order("id")
                .range(start, start + PAGE_SIZE - 1)
                .execute()
                .data
            )
            out.extend(page)
            if len(page) < PAGE_SIZE:
                return out
            start += PAGE_SIZE

    def upsert_raw_rounds(self, raws: list[dict]) -> None:
        rows = [{"id": raw["id"], "payload": raw, "fetched_at": _now()} for raw in raws]
        self._upsert("raw_rounds", rows)

    def upsert_companies(self, rows: list[CompanyRow]) -> None:
        # Only CompanyRow columns (plus updated_at) are sent, so website,
        # description, founded and details_fetched_at are never overwritten.
        now = _now()
        self._upsert("companies", [{**row, "updated_at": now} for row in rows])

    def upsert_rounds(self, rows: list[RoundRow]) -> None:
        now = _now()
        self._upsert("rounds", [{**row, "updated_at": now} for row in rows])

    def delete_rounds(self, ids: list[str]) -> int:
        deleted = 0
        for batch in _batches(ids, DELETE_BATCH):
            data = self._client.table("rounds").delete().in_("id", batch).execute().data
            deleted += len(data)
            self._client.table("raw_rounds").delete().in_("id", batch).execute()
        return deleted

    def all_raw_rounds(self) -> list[dict]:
        return [row["payload"] for row in self._read_all("raw_rounds", "id,payload")]

    def company_ids_missing_details(self, limit: int) -> list[str]:
        ids: list[str] = []
        while len(ids) < limit:
            size = min(PAGE_SIZE, limit - len(ids))
            page = (
                self._client.table("companies")
                .select("id")
                .is_("details_fetched_at", None)
                .order("id")
                .range(len(ids), len(ids) + size - 1)
                .execute()
                .data
            )
            ids.extend(row["id"] for row in page)
            if len(page) < size:
                break
        return ids

    def set_company_details(self, company_id: str, details: CompanyDetails) -> None:
        self._client.table("companies").update(
            {
                "website": details["website"],
                "description": details["description"],
                "founded": details["founded"],
                "details_fetched_at": _now(),
            }
        ).eq("id", company_id).execute()

    def last_successful_run_started_at(self) -> str | None:
        data = (
            self._client.table("sync_runs")
            .select("started_at")
            .eq("status", "success")
            .in_("command", list(WATERMARK_COMMANDS))
            .order("started_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        return data[0]["started_at"] if data else None

    def record_run(self, run: dict) -> None:
        self._client.table("sync_runs").insert(run).execute()

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for table in ("raw_rounds", "companies", "rounds"):
            response = (
                self._client.table(table).select("id", count="exact", head=True).execute()
            )
            result[table] = response.count or 0
        return result

    def all_rounds_with_company(self) -> list[dict]:
        companies: dict[str, Any] = {c["id"]: c for c in self._read_all("companies")}
        rows = self._read_all("rounds")
        return [{**row, "company": companies[row["company_id"]]} for row in rows]
