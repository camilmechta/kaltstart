"""Pure cleaning functions for raw Tech.eu funding round fields."""

import csv
import re
from pathlib import Path
from urllib.parse import urlsplit

SMALL_MAX_EUR = 3_000_000
MEDIUM_MAX_EUR = 15_000_000

_ALIASES_PATH = Path(__file__).with_name("city_aliases.csv")

_STAGE_SIZE = {
    "pre-seed": "small",
    "seed": "small",
    "series a": "medium",
    "series b": "large",
    "series c": "large",
    "series d+": "large",
    "growth/late": "large",
}

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def _load_aliases() -> dict[str, tuple[str | None, str | None]]:
    with _ALIASES_PATH.open(encoding="utf-8", newline="") as f:
        return {
            row["raw"].casefold(): (row["city"] or None, row["region"] or None)
            for row in csv.DictReader(f)
        }


_ALIASES = _load_aliases()


def clean_city(raw: str | None) -> tuple[str | None, str | None]:
    """Normalise a raw location into (city, region); unknown values are kept as cities."""
    if not raw:
        return None, None
    value = re.sub(r"\s+", " ", raw).strip()
    if not value:
        return None, None
    return _ALIASES.get(value.casefold(), (value, None))


def clean_investors(raw: list[str] | None) -> list[str]:
    """Strip names, drop empties and duplicates, keep first-seen order."""
    if not raw:
        return []
    return list(dict.fromkeys(name.strip() for name in raw if name and name.strip()))


def size_category(stage: str | None, amount_eur: int | None) -> str:
    """Return "small", "medium" or "large"; a known stage wins over the amount."""
    if stage:
        known = _STAGE_SIZE.get(stage.strip().casefold())
        if known:
            return known
    if amount_eur is None or amount_eur < SMALL_MAX_EUR:
        return "small"
    if amount_eur <= MEDIUM_MAX_EUR:
        return "medium"
    return "large"


def clean_website(raw: str | None) -> str | None:
    """Return a normalised URL, or None when the value is not a plausible website."""
    if not raw:
        return None
    value = raw.strip().rstrip("/")
    if not value:
        return None
    if not _SCHEME_RE.match(value):
        value = f"https://{value}"
    if re.search(r"\s", value):
        return None
    try:
        host = urlsplit(value).hostname
    except ValueError:
        return None
    if not host or "." not in host:
        return None
    return value
