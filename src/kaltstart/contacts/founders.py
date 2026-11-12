"""Founder names on legal-notice and team pages.

A name is trusted only when it stands next to a role word: in the same block
of the page, or in the block right before or after it (the usual layout of a
team card). This is a heuristic and the least reliable step of the scraper.
"""

import re

from bs4 import BeautifulSoup, Tag

from kaltstart.contacts.models import FoundFounder, Page

# Longest first, so that "Co-Founder" wins over "Founder".
ROLE_WORDS: tuple[str, ...] = (
    "Co-Founder", "Cofounder", "Founder", "Chief Executive Officer", "CEO",
    "Managing Director", "Mitgründerin", "Mitgründer", "Gründerin", "Gründer",
    "Geschäftsführerin", "Geschäftsführer", "Geschäftsleitung",
)
_PAGE_KINDS = ("legal", "team")
_BLOCKS = ("p", "li", "td", "th", "div", "span", "dd", "dt",
           "h1", "h2", "h3", "h4", "h5", "h6")
_ROLE_PATTERNS = tuple(
    (role, re.compile(rf"(?<![\w-]){re.escape(role)}(?![\w-])", re.IGNORECASE))
    for role in ROLE_WORDS)
_TITLES = re.compile(r"\b(?:Dr|Prof|Mag|Ing|Dipl\.-Ing)\.", re.IGNORECASE)
_WORD = r"[A-ZÀ-ÖØ-Þ][^\W\d_]*(?:[-'’][^\W\d_]+)*"
_PARTICLE = r"(?:von|van|de|del|di|der|den)"
_NAME = re.compile(rf"{_WORD}(?:\s+(?:{_PARTICLE}\s+)*{_WORD}){{1,3}}")
_COMPANY_SUFFIXES = ("AG", "GmbH", "SA", "Sàrl", "Ltd", "Inc")
_NOT_NAMES = ("Award", "Collective", "Office", "Year", "Team")


def _text(element: Tag) -> str:
    return " ".join(element.get_text(" ").split())


def _is_leaf(element: Tag) -> bool:
    return element.find(_BLOCKS) is None


def _role_in(text: str) -> str | None:
    for role, pattern in _ROLE_PATTERNS:
        if pattern.search(text):
            return role
    return None


def _names_in(text: str) -> list[str]:
    for _role, pattern in _ROLE_PATTERNS:
        text = pattern.sub(" | ", text)
    text = _TITLES.sub(" ", text)
    names = []
    for match in _NAME.finditer(text):
        words = match.group(0).split()
        if any(w in _COMPANY_SUFFIXES or w in _NOT_NAMES for w in words):
            continue
        names.append(" ".join(words))
    return names


def extract_founders(page: Page) -> list[FoundFounder]:
    """One entry per distinct name found next to a role word, in page order."""
    if page.kind not in _PAGE_KINDS:
        return []
    soup = BeautifulSoup(page.html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    found: dict[str, FoundFounder] = {}
    for block in soup.find_all(_BLOCKS):
        if not _is_leaf(block):
            continue
        role = _role_in(_text(block))
        if role is None:
            continue
        names = _names_in(_text(block))
        if not names:
            for sibling in (block.find_previous_sibling(_BLOCKS),
                            block.find_next_sibling(_BLOCKS)):
                if sibling is not None and _is_leaf(sibling) \
                        and _role_in(_text(sibling)) is None:
                    names = _names_in(_text(sibling))
                    if names:
                        break
        for name in names:
            found.setdefault(name, FoundFounder(name, role, page.url))
    return list(found.values())
