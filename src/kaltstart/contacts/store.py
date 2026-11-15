"""Where contacts are kept: the operations the nightly run needs, and an
in-memory version of them for tests."""

from datetime import date
from typing import Protocol

_STATE = ("contacts_checked_at", "contacts_outcome", "contacts_attempts", "contacts_next_at")
CANDIDATE_COLUMNS = ("id", "name", "website", "created_at", *_STATE)


class ContactStore(Protocol):
    def candidate_companies(self, country: str) -> list[dict]:
        """Companies of the country that have a website, with their reading state."""

    def company_ids_with_round_since(self, cutoff: date) -> set[str]: ...

    def company_ids_with_contacts(self) -> set[str]:
        """Companies with at least one stored address or person."""

    def company_ids_with_people(self) -> set[str]: ...

    def exclusions(self) -> list[dict]:
        """Rows `{"company_id", "person_key"}`; a null key excludes the whole company."""

    def replace_contacts(self, company_id: str, emails: list[dict],
                         people: list[dict]) -> None:
        """Delete everything stored for the company, then store this reading."""

    def delete_contacts(self, company_ids: list[str]) -> None: ...

    def set_contact_state(self, company_id: str, *, checked_at: str, outcome: str,
                          attempts: int, next_at: str) -> None: ...

    def record_contact_run(self, run: dict) -> None: ...


class InMemoryContactStore:
    """A `ContactStore` in plain lists, for tests."""

    def __init__(self) -> None:
        self.companies: dict[str, dict] = {}
        self.rounds: list[dict] = []
        self.emails: list[dict] = []
        self.people: list[dict] = []
        self.excluded: list[dict] = []
        self.runs: list[dict] = []

    def add_company(self, id: str, name: str, website: str | None,
                    country: str = "Switzerland",
                    created_at: str = "2026-01-01T00:00:00+00:00") -> None:
        self.companies[id] = {
            "id": id, "name": name, "website": website, "country": country,
            "created_at": created_at, "contacts_checked_at": None,
            "contacts_outcome": None, "contacts_attempts": 0, "contacts_next_at": None}

    def candidate_companies(self, country: str) -> list[dict]:
        return [{column: row[column] for column in CANDIDATE_COLUMNS}
                for row in self.companies.values()
                if row["country"] == country and row["website"]]

    def company_ids_with_round_since(self, cutoff: date) -> set[str]:
        return {r["company_id"] for r in self.rounds if r["date"] >= cutoff.isoformat()}

    def company_ids_with_contacts(self) -> set[str]:
        return {row["company_id"] for row in [*self.emails, *self.people]}

    def company_ids_with_people(self) -> set[str]:
        return {row["company_id"] for row in self.people}

    def exclusions(self) -> list[dict]:
        return list(self.excluded)

    def replace_contacts(self, company_id: str, emails: list[dict],
                         people: list[dict]) -> None:
        self.delete_contacts([company_id])
        self.emails += emails
        self.people += people

    def delete_contacts(self, company_ids: list[str]) -> None:
        self.emails = [e for e in self.emails if e["company_id"] not in company_ids]
        self.people = [p for p in self.people if p["company_id"] not in company_ids]

    def set_contact_state(self, company_id: str, *, checked_at: str, outcome: str,
                          attempts: int, next_at: str) -> None:
        self.companies[company_id].update(
            contacts_checked_at=checked_at, contacts_outcome=outcome,
            contacts_attempts=attempts, contacts_next_at=next_at)

    def record_contact_run(self, run: dict) -> None:
        self.runs.append(run)
