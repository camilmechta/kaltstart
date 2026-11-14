"""Polite download of the few pages of one company site.

Hard rules enforced here: a host's robots.txt is read before any other
request to that host; only the company's own site is ever requested, also
when a page redirects elsewhere; every request, redirect hops included, waits
for the minimum interval.
"""

import time
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from kaltstart.contacts.models import FetchOutcome, Page
from kaltstart.contacts.pages import choose_links
from kaltstart.contacts.site import is_social, same_site, site_host

MAX_REDIRECTS = 5
USER_AGENT_TOKEN = "python-httpx"   # the product token of the default User-Agent
_REDIRECTS = (301, 302, 303, 307, 308)
_FORBID_ALL = object()              # robots.txt answered with a server error: assume disallowed
_NO_ANSWER = object()               # robots.txt could not be reached at all


def default_http_client() -> httpx.Client:
    """Client used for real runs: 15-second timeout, the library's own headers."""
    return httpx.Client(timeout=15, follow_redirects=True)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


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
        self._robots_by_origin: dict[str, object] = {}

    def fetch_site(self, website: str) -> FetchOutcome:
        """Read the home page, then the pages chosen from its links."""
        self._last_request_at = None
        self._robots_by_origin = {}
        value = website.strip()
        if "://" not in value:
            value = "https://" + value
        home_url = value if urlsplit(value).path.strip("/") else _origin(value) + "/"
        hosts = [site_host(value)]
        if is_social(home_url):
            return FetchOutcome("unreachable", (), tuple(hosts))

        # A redirect of the home page may lead to the company's new domain.
        status, final_url, html = self._fetch(home_url, hosts, may_add_host=True)
        if status != "ok":
            failed = "robots_forbidden" if status == "forbidden" else "unreachable"
            return FetchOutcome(failed, (), tuple(hosts))

        pages = [Page(final_url, "home", html)]
        for url, kind in choose_links(html, final_url, hosts,
                                      max_links=self._max_pages - 1):
            if len(pages) >= self._max_pages:
                break
            status, page_url, body = self._fetch(url, hosts, may_add_host=False)
            if status == "ok":
                pages.append(Page(page_url, kind, body))
        return FetchOutcome("ok", tuple(pages), tuple(hosts))

    def _fetch(self, url: str, hosts: list[str],
               may_add_host: bool) -> tuple[str, str, str]:
        """`(status, final_url, html)` with status `ok`, `forbidden` or `failed`.

        Redirects are followed by hand, so that each hop is checked before it
        is requested.
        """
        for _hop in range(MAX_REDIRECTS + 1):
            if is_social(url):
                return "failed", url, ""
            new_host = not same_site(url, hosts)
            if new_host and not may_add_host:
                return "failed", url, ""
            if self._rules(url) is _NO_ANSWER:
                return "failed", url, ""    # nothing is fetched without its robots.txt
            if not self._allowed(url):
                return "forbidden", url, ""
            if new_host:
                hosts.append(site_host(url))
            response = self._get(url)
            if response is None:
                return "failed", url, ""
            location = response.headers.get("location")
            if response.status_code in _REDIRECTS and location:
                url = urljoin(url, location)
                continue
            if response.status_code != 200:
                return "failed", url, ""
            if "html" not in response.headers.get("content-type", "").lower():
                return "failed", url, ""
            if len(response.content) > self._max_bytes:
                return "failed", url, ""
            return "ok", url, _text(response)
        return "failed", url, ""

    def _get(self, url: str) -> httpx.Response | None:
        """One request, after the minimum wait. Never follows a redirect itself."""
        if self._last_request_at is not None:
            remaining = self._min_interval_s - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = time.monotonic()
        try:
            return self._http.get(url, follow_redirects=False)
        except httpx.HTTPError:
            return None

    def _rules(self, url: str):
        """The robots.txt of the URL's own origin, read first if needed."""
        origin = _origin(url)
        if origin not in self._robots_by_origin:
            self._robots_by_origin[origin] = self._read_robots(origin)
        return self._robots_by_origin[origin]

    def _allowed(self, url: str) -> bool:
        rules = self._rules(url)
        if rules is _FORBID_ALL or rules is _NO_ANSWER:
            return False
        return rules is None or rules.can_fetch(USER_AGENT_TOKEN, url)

    def _read_robots(self, origin: str):
        """A parser, None when there are no rules, `_FORBID_ALL` or `_NO_ANSWER`.

        As RFC 9309 asks: a missing file (4xx) means no restriction, and a
        file that cannot be read means nothing is fetched. A server error is
        the site's doing and is reported as forbidden; no answer at all (a
        network failure, maybe our own) is reported as unreachable.
        """
        url = origin + "/robots.txt"
        host = [site_host(origin)]
        for _hop in range(MAX_REDIRECTS + 1):
            if is_social(url) or not same_site(url, host):
                return None     # redirected off the site: nothing we may read
            response = self._get(url)
            if response is None:
                return _NO_ANSWER
            if response.status_code >= 500:
                return _FORBID_ALL
            location = response.headers.get("location")
            if response.status_code in _REDIRECTS and location:
                url = urljoin(url, location)
                continue
            if response.status_code != 200:
                return None
            if "html" in response.headers.get("content-type", "").lower():
                return None
            parser = RobotFileParser()
            parser.parse(_text(response).splitlines())
            return parser
        return _FORBID_ALL


def _text(response: httpx.Response) -> str:
    try:
        return response.content.decode(response.encoding or "utf-8", errors="replace")
    except LookupError:
        return response.content.decode("utf-8", errors="replace")
