"""Values exchanged between the contact scraper's modules."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    url: str
    kind: str            # "home" | "legal" | "contact" | "team" | "careers"
    html: str


@dataclass(frozen=True)
class FetchOutcome:
    status: str          # "ok" | "robots_forbidden" | "unreachable"
    pages: tuple[Page, ...]
    hosts: tuple[str, ...]   # accepted site hosts: the sample's, and the home page's final host


@dataclass(frozen=True)
class FoundEmail:
    address: str         # lower case
    type: str            # "personal" | "careers" | "generic"
    source_url: str


@dataclass(frozen=True)
class FoundFounder:
    name: str
    role: str
    source_url: str


@dataclass(frozen=True)
class ProposedContact:
    address: str
    founder_name: str | None
    confidence: str      # "high" | "medium" | "low"


@dataclass(frozen=True)
class CompanyResult:
    company_id: str
    name: str
    website: str
    size_category: str   # "small" | "medium" | "large"
    pages_fetched: tuple[str, ...]
    emails: tuple[FoundEmail, ...]
    founders: tuple[FoundFounder, ...]
    contact: ProposedContact | None
    failure: str | None  # None, or one of scrape.FAILURES
