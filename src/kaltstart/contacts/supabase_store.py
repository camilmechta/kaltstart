"""Supabase-backed ContactStore (service-role key, used by the nightly run)."""

import os
from datetime import date
from typing import Callable

from supabase import Client, create_client

from kaltstart.contacts.store import CANDIDATE_COLUMNS

PAGE_SIZE = 1000
WRITE_BATCH = 500
DELETE_BATCH = 100      # ids are 36-character UUIDs, and they go into the URL
_CONTACT_TABLES = ("contact_emails", "contact_people")


class SupabaseContactStore:
    def __init__(self, client: Client) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "SupabaseContactStore":
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        return cls(create_client(url, key))

    def _read_all(self, table: str, columns: str, order: tuple[str, ...],
                  narrow: Callable = lambda query: query) -> list[dict]:
        """Read every matching row, paging past the 1000-row response cap.

        `order` must name a unique key: pages of an ambiguous order can
        skip a row.
        """
        out: list[dict] = []
        while True:
            query = narrow(self._client.table(table).select(columns))
            for column in order:
                query = query.order(column)
            page = query.range(len(out), len(out) + PAGE_SIZE - 1).execute().data
            out.extend(page)
            if len(page) < PAGE_SIZE:
                return out

    def _company_ids(self, table: str, order: tuple[str, ...],
                     narrow: Callable = lambda query: query) -> set[str]:
        return {row["company_id"] for row in self._read_all(table, "company_id", order, narrow)}

    def candidate_companies(self, country: str) -> list[dict]:
        return self._read_all(
            "companies", ",".join(CANDIDATE_COLUMNS), ("id",),
            lambda query: query.eq("country", country).not_.is_("website", "null"))

    def company_ids_with_round_since(self, cutoff: date) -> set[str]:
        return self._company_ids(
            "rounds", ("id",), lambda query: query.gte("date", cutoff.isoformat()))

    def company_ids_with_contacts(self) -> set[str]:
        return (self._company_ids("contact_emails", ("company_id", "address"))
                | self.company_ids_with_people())

    def company_ids_with_people(self) -> set[str]:
        return self._company_ids("contact_people", ("company_id", "name"))

    def exclusions(self) -> list[dict]:
        return self._read_all("contact_exclusions", "company_id,person_key", ("id",))

    def replace_contacts(self, company_id: str, emails: list[dict],
                         people: list[dict]) -> None:
        self.delete_contacts([company_id])
        for table, rows in zip(_CONTACT_TABLES, (emails, people)):
            for start in range(0, len(rows), WRITE_BATCH):
                self._client.table(table).insert(rows[start:start + WRITE_BATCH]).execute()

    def delete_contacts(self, company_ids: list[str]) -> None:
        for start in range(0, len(company_ids), DELETE_BATCH):
            batch = company_ids[start:start + DELETE_BATCH]
            for table in _CONTACT_TABLES:
                self._client.table(table).delete().in_("company_id", batch).execute()

    def set_contact_state(self, company_id: str, *, checked_at: str, outcome: str,
                          attempts: int, next_at: str) -> None:
        self._client.table("companies").update({
            "contacts_checked_at": checked_at, "contacts_outcome": outcome,
            "contacts_attempts": attempts, "contacts_next_at": next_at,
        }).eq("id", company_id).execute()

    def record_contact_run(self, run: dict) -> None:
        self._client.table("contact_runs").insert(run).execute()
