"""Addresses published on a page."""

import re
from typing import Iterable
from urllib.parse import unquote

from bs4 import BeautifulSoup

from kaltstart.contacts.models import Page
from kaltstart.contacts.site import on_company_domain, visible_text

TOOLING_DOMAINS = ("sentry.io", "wixpress.com")
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

_ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Bracketed disguise, e.g. "hello [at] example [dot] ch". Lower case only:
# an address is written in lower case, a capitalised "Jobs [at] Example.ch"
# is a heading. Bare words ("hello at example.ch") are never read as an
# address, because any title of the form "Jobs at Example.ch" would become one.
_AT = r"\s*[\[(]\s*(?:at|AT)\s*[\])]\s*"
_DOT = r"\s*(?:\.|[\[(]\s*(?:dot|DOT)\s*[\])])\s*"
_DISGUISED = re.compile(
    rf"(?<![A-Za-z0-9._%+-])([a-z0-9._%+-]+){_AT}([a-z0-9-]+(?:{_DOT}[a-z0-9-]+)+)(?![A-Za-z0-9-])")
_DOT_ONLY = re.compile(_DOT)


def _candidates(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.lower().startswith("mailto:"):
            recipients = unquote(href[len("mailto:"):].split("?", 1)[0])
            found += [r.strip() for r in recipients.split(",")]
    text = visible_text(html)
    found += _ADDRESS.findall(text)
    found += [f"{local}@{_DOT_ONLY.sub('.', domain)}"
              for local, domain in _DISGUISED.findall(text)]
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
