"""HTTP client for the Tech.eu Funding Explorer API.

The only module that talks to the network. It enforces a request budget and a
minimum interval between requests (Tech.eu quotas: 120/minute, 600/hour,
2000/day) and retries transient failures.
"""
import time
from typing import Callable, Iterator

import httpx

BASE_URL = "https://funding.tech.eu/api/v1"
PAGE_SIZE = 100
MAX_ATTEMPTS = 3
RETRY_DELAYS_S = (5, 15)


class TechEuError(Exception):
    """A request to the Tech.eu API failed."""


class FilterMismatchError(TechEuError):
    """The API applied filters different from the ones that were sent."""


class BudgetExhaustedError(TechEuError):
    """The configured maximum number of requests has been reached."""


class TechEuClient:
    def __init__(self, http: httpx.Client, min_interval_s: float = 7.0,
                 max_requests: int = 1500,
                 sleep: Callable[[float], None] = time.sleep):
        self._http = http
        self._min_interval_s = min_interval_s
        self._max_requests = max_requests
        self._sleep = sleep
        self._last_request_at: float | None = None
        self.requests_made = 0

    def iter_rounds(self, country: str, date_from: str,
                    date_to: str) -> Iterator[dict]:
        sent = {"country": country, "from": date_from, "to": date_to}
        cursor = None
        while True:
            params = {**sent, "limit": PAGE_SIZE}
            if cursor:
                params["after"] = cursor
            page = self._get("/rounds", params)
            applied = page.get("appliedFilters") or {}
            for key, value in sent.items():
                if applied.get(key) != value:
                    raise FilterMismatchError(
                        f"API applied {key}={applied.get(key)!r}, "
                        f"expected {value!r}")
            yield from page["data"]
            cursor = page.get("nextCursor")
            if not cursor:
                return

    def fetch_changes(self, since: str) -> tuple[list[dict], list[str]]:
        added: list[dict] = []
        removed: list[str] = []
        seen_cursors: set[str] = set()
        cursor = None
        while True:
            params = {"since": since, "limit": PAGE_SIZE}
            if cursor:
                params["after"] = cursor
            page = self._get("/changes", params)
            added.extend(page.get("data") or [])
            for entry in page.get("removed") or []:
                removed.append(entry["id"] if isinstance(entry, dict) else entry)
            cursor = page.get("nextCursor")
            if not cursor or cursor in seen_cursors:
                return added, removed
            seen_cursors.add(cursor)

    def get_company(self, company_id: str) -> dict:
        return self._get(f"/companies/{company_id}", {})

    def _wait_for_throttle(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self._min_interval_s - (
            time.monotonic() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    def _get(self, path: str, params: dict) -> dict:
        last_problem = ""
        for attempt in range(MAX_ATTEMPTS):
            if attempt > 0:
                self._sleep(RETRY_DELAYS_S[attempt - 1])
            if self.requests_made >= self._max_requests:
                raise BudgetExhaustedError(
                    f"request budget of {self._max_requests} exhausted")
            self._wait_for_throttle()
            self.requests_made += 1
            self._last_request_at = time.monotonic()
            try:
                response = self._http.get(path, params=params)
            except httpx.TransportError as exc:
                last_problem = f"{type(exc).__name__}: {exc}"
                continue
            status = response.status_code
            if status == 429 or status >= 500:
                last_problem = f"HTTP {status}"
                continue
            if status >= 400:
                raise TechEuError(
                    f"GET {path} failed with HTTP {status}"
                    f"{_error_detail(response)}")
            return response.json()
        raise TechEuError(
            f"GET {path} failed after {MAX_ATTEMPTS} attempts ({last_problem})")


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if isinstance(body, dict) and body.get("error"):
        return f": {body['error']}"
    return ""
