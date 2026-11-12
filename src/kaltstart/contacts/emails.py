"""Addresses published on a page."""

import re
from typing import Iterable

from bs4 import BeautifulSoup

from kaltstart.contacts.models import Page
from kaltstart.contacts.site import on_company_domain, visible_text

TOOLING_DOMAINS = ("sentry.io", "wixpress.com")
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

_ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BRACKET_AT = re.compile(r"\s*[\[(]\s*at\s*[\])]\s*", re.IGNORECASE)
_BRACKET_DOT = re.compile(r"\s*[\[(]\s*dot\s*[\])]\s*", re.IGNORECASE)
# "hello at example dot ch": only trusted as the whole text of an element.
_BARE_WORDS = re.compile(
    r"^([A-Za-z0-9._%+-]+)\s+at\s+"
    r"([A-Za-z0-9-]+(?:(?:\s+dot\s+|\.)[A-Za-z0-9-]+)+)$", re.IGNORECASE)
_BARE_DOT = re.compile(r"\s+dot\s+", re.IGNORECASE)


def _candidates(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.lower().startswith("mailto:"):
            found.append(href[len("mailto:"):].split("?", 1)[0])
    text = _BRACKET_DOT.sub(".", _BRACKET_AT.sub("@", visible_text(html)))
    found += _ADDRESS.findall(text)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for element in soup.find_all(True):
        match = _BARE_WORDS.match(" ".join(element.get_text(" ").split()))
        if match:
            found.append(f"{match.group(1)}@{_BARE_DOT.sub('.', match.group(2))}")
    return found


def _is_noise(domain: str) -> bool:
    if domain.endswith(_IMAGE_EXTENSIONS):
        return True
    return any(domain == d or domain.endswith("." + d) for d in TOOLING_DOMAINS)


def extract_addresses(page: Page, hosts: Iterable[str]) -> tuple[list[str], int]:
    """Addresses on the company's domain, and how many others were seen.

    Kept addresses are lower case, in order of first appearance, without
    duplicates. Addresses of website tooling are ignored altogether.
    """
    hosts = tuple(hosts)
    kept: list[str] = []
    others: set[str] = set()
    for candidate in _candidates(page.html):
        address = candidate.strip().strip(".").lower()
        if not _ADDRESS.fullmatch(address):
            continue
        domain = address.rsplit("@", 1)[1]
        if _is_noise(domain):
            continue
        if on_company_domain(domain, hosts):
            if address not in kept:
                kept.append(address)
        else:
            others.add(address)
    return kept, len(others)
