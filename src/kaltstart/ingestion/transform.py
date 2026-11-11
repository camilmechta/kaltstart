"""Map raw Tech.eu API payloads to company and round rows."""

from typing import TypedDict

from kaltstart.ingestion.cleaning import (
    clean_city,
    clean_investors,
    clean_website,
    size_category,
)


class CompanyRow(TypedDict):
    id: str
    name: str
    country: str
    city_raw: str | None
    city: str | None
    region: str | None
    sectors: list[str]
    techeu_url: str


class RoundRow(TypedDict):
    id: str
    company_id: str
    date: str
    stage: str | None
    raw_round_type: str | None
    amount_eur: int | None
    amount_native: float | None
    currency: str | None
    size_category: str
    investors: list[str]
    source_url: str
    source_domain: str | None
    confidence: str | None


class CompanyDetails(TypedDict):
    website: str | None
    description: str | None
    founded: int | None


def _text(value: str | None) -> str | None:
    """Return the string unchanged, or None when it is missing or blank."""
    if value is None or not value.strip():
        return None
    return value


def _number(value):
    """Map None and "" to None; return any other value unchanged."""
    return None if value is None or value == "" else value


def transform_round(raw: dict) -> tuple[CompanyRow, RoundRow]:
    """Split one raw round into a company row and a round row."""
    raw_company = raw["company"]
    city_raw = _text(raw_company.get("city"))
    city, region = clean_city(city_raw)
    company: CompanyRow = {
        "id": raw_company["id"],
        "name": raw_company["name"],
        "country": raw_company["country"],
        "city_raw": city_raw,
        "city": city,
        "region": region,
        "sectors": raw_company.get("sectors") or [],
        "techeu_url": raw_company["pageUrl"],
    }
    stage = _text(raw.get("stage"))
    amount_eur = _number(raw.get("amountEur"))
    if isinstance(amount_eur, float):
        amount_eur = round(amount_eur)  # amount_eur is a bigint column
    rnd: RoundRow = {
        "id": raw["id"],
        "company_id": raw_company["id"],
        "date": raw["date"],
        "stage": stage,
        "raw_round_type": _text(raw.get("rawRoundType")),
        "amount_eur": amount_eur,
        "amount_native": _number(raw.get("amountNative")),
        "currency": _text(raw.get("currency")),
        "size_category": size_category(stage, amount_eur),
        "investors": clean_investors(raw.get("investors")),
        "source_url": raw["pageUrl"],
        "source_domain": _text((raw.get("source") or {}).get("domain")),
        "confidence": _text(raw.get("confidence")),
    }
    return company, rnd


def transform_company_details(raw: dict) -> CompanyDetails:
    """Extract website, description and founding year from a company payload."""
    description = _text(raw.get("description"))
    return {
        "website": clean_website(raw.get("website")),
        "description": description.strip() if description else None,
        "founded": _number(raw.get("founded")),
    }
