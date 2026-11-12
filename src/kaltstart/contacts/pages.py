"""Which links of a home page are worth reading."""

from typing import Iterable
from urllib.parse import urljoin, urlsplit

from kaltstart.contacts.site import links, same_site

KINDS = ("legal", "contact", "team", "careers")
KEYWORDS: dict[str, tuple[str, ...]] = {
    "legal": ("impressum", "imprint", "legal"),
    "contact": ("contact", "kontakt"),
    "team": ("team", "about", "ueber-uns", "über uns", "about-us", "company",
             "unternehmen"),
    "careers": ("careers", "career", "jobs", "karriere", "join"),
}
FALLBACK_PATHS: tuple[tuple[str, str], ...] = (
    ("/impressum", "legal"), ("/imprint", "legal"), ("/contact", "contact"),
    ("/team", "team"), ("/about", "team"), ("/careers", "careers"),
    ("/jobs", "careers"),
)
_PAGE_EXTENSIONS = ("", ".html", ".htm", ".php", ".aspx")


def _kind(url: str, text: str) -> str | None:
    haystack = f"{text} {urlsplit(url).path}".lower()
    for kind in KINDS:
        if any(keyword in haystack for keyword in KEYWORDS[kind]):
            return kind
    return None


def _is_page(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    last = parts.path.rsplit("/", 1)[-1]
    extension = "." + last.rsplit(".", 1)[-1].lower() if "." in last else ""
    return extension in _PAGE_EXTENSIONS


def choose_links(home_html: str, home_url: str, hosts: Iterable[str],
                 max_links: int = 7, per_kind: int = 2) -> list[tuple[str, str]]:
    """Return `(url, kind)` for the pages to read after the home page.

    Links are taken by kind in priority order, at most `per_kind` of each and
    `max_links` in total. Without any matching link, the fixed paths are tried.
    """
    hosts = tuple(hosts)
    home = home_url.rstrip("/")
    by_kind: dict[str, list[str]] = {kind: [] for kind in KINDS}
    seen = set()
    for url, text in links(home_html, home_url):
        if url in seen or url.rstrip("/") == home:
            continue
        if not _is_page(url) or not same_site(url, hosts):
            continue
        kind = _kind(url, text)
        if kind and len(by_kind[kind]) < per_kind:
            seen.add(url)
            by_kind[kind].append(url)
    chosen = [(url, kind) for kind in KINDS for url in by_kind[kind]]
    if not chosen:
        chosen = [(urljoin(home_url, path), kind) for path, kind in FALLBACK_PATHS]
    return chosen[:max_links]
