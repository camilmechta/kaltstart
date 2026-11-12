"""Which links of a home page are worth reading."""

import re
from typing import Iterable
from urllib.parse import urljoin, urlsplit

from kaltstart.contacts.site import links, same_site, site_host

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
# Pages that carry "legal" in their name but never the people behind a company.
_NOT_A_LEGAL_NOTICE = ("privacy", "datenschutz", "terms", "agb", "cookie", "cookies",
                       "nutzungsbedingungen", "disclaimer")
_LEGAL_NOTICE = ("impressum", "imprint")


def _words(value: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", value.lower())


def _kind(url: str, text: str) -> tuple[str, int] | None:
    """`(kind, rank)`: the kind of page a link leads to, and how sure the keyword is.

    Keywords match whole words, so "join" does not match "joint-venture".
    """
    words = _words(f"{text} {urlsplit(url).path}")
    if any(w in words for w in _NOT_A_LEGAL_NOTICE) \
            and not any(w in words for w in _LEGAL_NOTICE):
        return None
    haystack = " " + " ".join(words) + " "
    for kind in KINDS:
        for rank, keyword in enumerate(KEYWORDS[kind]):
            if " " + " ".join(_words(keyword)) + " " in haystack:
                return kind, rank
    return None


def _is_page(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    last = parts.path.rsplit("/", 1)[-1]
    extension = "." + last.rsplit(".", 1)[-1].lower() if "." in last else ""
    return extension in _PAGE_EXTENSIONS


def _same_page_key(url: str) -> tuple[str, str]:
    """Two spellings of one page (trailing slash, query, www) share a key."""
    return site_host(url), urlsplit(url).path.rstrip("/")


def choose_links(home_html: str, home_url: str, hosts: Iterable[str],
                 max_links: int = 7, per_kind: int = 2) -> list[tuple[str, str]]:
    """Return `(url, kind)` for the pages to read after the home page.

    Links are taken by kind in priority order, the surest keyword first, at
    most `per_kind` of each and `max_links` in total. Without any matching
    link, the fixed paths are tried.
    """
    hosts = tuple(hosts)
    seen = {_same_page_key(home_url)}
    by_kind: dict[str, list[tuple[int, str]]] = {kind: [] for kind in KINDS}
    for url, text in links(home_html, home_url):
        if not _is_page(url) or not same_site(url, hosts):
            continue
        key = _same_page_key(url)
        found = _kind(url, text)
        if key in seen or found is None:
            continue
        seen.add(key)
        by_kind[found[0]].append((found[1], url))
    chosen = []
    for kind in KINDS:
        ranked = sorted(by_kind[kind], key=lambda item: item[0])   # stable
        chosen += [(url, kind) for _rank, url in ranked[:per_kind]]
    if not chosen:
        chosen = [(urljoin(home_url, path), kind) for path, kind in FALLBACK_PATHS]
    return chosen[:max_links]
