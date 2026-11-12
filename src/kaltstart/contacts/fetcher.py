"""Polite download of the few pages of one company site."""

import time
from typing import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from kaltstart.contacts.models import FetchOutcome, Page
from kaltstart.contacts.pages import choose_links
from kaltstart.contacts.site import same_site, site_host


def default_http_client() -> httpx.Client:
    """Client used for real runs: 15-second timeout, the library's own headers."""
    return httpx.Client(timeout=15, follow_redirects=True)


class SiteFetcher:
    def __init__(self, http: httpx.Client, min_interval_s: float = 2.0,
                 max_pages: int = 8, max_bytes: int = 2_000_000,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._http = http
        self._min_interval_s = min_interval_s
        self._max_pages = max_pages
        self._max_bytes = max_bytes
        self._sleep = sleep
        self._last_request_at: float | None = None

    def fetch_site(self, website: str) -> FetchOutcome:
        """Read robots.txt, the home page, then the pages chosen from its links."""
        self._last_request_at = None
        value = website.strip()
        if "://" not in value:
            value = "https://" + value
        parts = urlsplit(value)
        origin = f"{parts.scheme}://{parts.netloc}"
        home_url = value if parts.path.strip("/") else origin + "/"
        hosts = [site_host(value)]

        robots = self._robots(origin)
        if not _allowed(robots, home_url):
            return FetchOutcome("robots_forbidden", (), tuple(hosts))

        home = self._page(home_url)
        if home is None:
            return FetchOutcome("unreachable", (), tuple(hosts))
        final_url, html = home
        if not same_site(final_url, hosts):
            # The company moved to another domain: that domain is its site now,
            # and its own robots.txt applies from here on.
            hosts.append(site_host(final_url))
            final = urlsplit(final_url)
            robots = self._robots(f"{final.scheme}://{final.netloc}")
            if not _allowed(robots, final_url):
                return FetchOutcome("robots_forbidden", (), tuple(hosts))

        pages = [Page(final_url, "home", html)]
        for url, kind in choose_links(html, final_url, hosts,
                                      max_links=self._max_pages - 1):
            if len(pages) >= self._max_pages:
                break
            if not _allowed(robots, url):
                continue
            fetched = self._page(url)
            if fetched is None or not same_site(fetched[0], hosts):
                continue
            pages.append(Page(fetched[0], kind, fetched[1]))
        return FetchOutcome("ok", tuple(pages), tuple(hosts))

    def _get(self, url: str) -> httpx.Response | None:
        if self._last_request_at is not None:
            remaining = self._min_interval_s - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = time.monotonic()
        try:
            return self._http.get(url)
        except httpx.HTTPError:
            return None

    def _robots(self, origin: str) -> RobotFileParser | None:
        """Rules of the site, or None when there are none to obey."""
        response = self._get(origin + "/robots.txt")
        if response is None or response.status_code != 200:
            return None
        if "html" in response.headers.get("content-type", "").lower():
            return None
        parser = RobotFileParser()
        parser.parse(_text(response).splitlines())
        return parser

    def _page(self, url: str) -> tuple[str, str] | None:
        """`(final_url, html)`, or None for anything that is not a readable page."""
        response = self._get(url)
        if response is None or response.status_code != 200:
            return None
        if "html" not in response.headers.get("content-type", "").lower():
            return None
        if len(response.content) > self._max_bytes:
            return None
        return str(response.url), _text(response)


def _allowed(robots: RobotFileParser | None, url: str) -> bool:
    return robots is None or robots.can_fetch("*", url)


def _text(response: httpx.Response) -> str:
    try:
        return response.content.decode(response.encoding or "utf-8", errors="replace")
    except LookupError:
        return response.content.decode("utf-8", errors="replace")
