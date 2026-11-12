"""Founder names on legal-notice and team pages.

A name is trusted only when it stands next to a role word: in the same block
of the page, or in the block right before or after it (the usual layout of a
team card). This is a heuristic and the least reliable step of the scraper;
when in doubt it returns nothing, because a wrong name ends up in a mail.
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
_SKIPPED = ("script", "style", "noscript", "nav", "header", "blockquote")
_ROLE = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(r) for r in ROLE_WORDS) + r")(?![\w-])",
    re.IGNORECASE)
# "Former CEO", "Head of CEO Office", "Founder Associate" are not the role.
_NOT_A_ROLE_BEFORE = re.compile(
    r"(?:former|ex|ehemaliger|ehemalige|head of|assistant to(?: the)?)[\s-]*$",
    re.IGNORECASE)
_NOT_A_ROLE_AFTER = re.compile(
    r"^\s*(?:associate|office|assistant|in residence)\b", re.IGNORECASE)
_TITLES = re.compile(r"\b(?:Dr|Prof|Mag|Ing|Dipl\.-Ing)\.", re.IGNORECASE)
_WORD = r"[A-ZÀ-ÖØ-Þ][^\W\d_]*(?:[-'’][^\W\d_]+)*"
_PARTICLE = r"(?:von|van|de|del|di|der|den)"
_NAME = re.compile(rf"{_WORD}(?:\s+(?:{_PARTICLE}\s+)*{_WORD}){{1,3}}")
# A name that follows one of these words names an organisation, not a person.
_ORGANISATION_BEFORE = re.compile(r"\b(?:of|at|bei|for|für|by|von der)\s*$", re.IGNORECASE)
_COMPANY_SUFFIXES = ("AG", "GmbH", "SA", "Sàrl", "Ltd", "Inc", "KG", "UG", "SE")
_NOT_NAME_WORDS = frozenset(w.lower() for w in (
    "About", "Us", "Our", "From", "Dear", "Friends", "Message", "Story", "The",
    "And", "Team", "Award", "Collective", "Office", "Year", "Contact", "Home",
    "Meet", "Welcome", "Read", "More", "Person", "Stelle", "Und", "Der", "Die",
    "Das", "Unser", "Unsere", "Über", "Uns", "Mehr", "Kontakt", "Impressum",
    "Investor", "Advisor", "Board", "Member"))


def _text(element: Tag) -> str:
    return " ".join(element.get_text(" ").split())


def _is_leaf(element: Tag) -> bool:
    return element.find(_BLOCKS) is None


def _roles(text: str) -> list[re.Match]:
    return [m for m in _ROLE.finditer(text)
            if not _NOT_A_ROLE_BEFORE.search(text[:m.start()])
            and not _NOT_A_ROLE_AFTER.match(text[m.end():])]


def _canonical(role: str) -> str:
    return next(r for r in ROLE_WORDS if r.lower() == role.lower())


def _display(word: str) -> str:
    return word.capitalize() if len(word) > 1 and word.isupper() else word


def _names(text: str) -> list[tuple[str, int, int]]:
    """`(name, start, end)` for every plausible person name in `text`."""
    # Roles and titles are blanked out, keeping every position unchanged.
    masked = _ROLE.sub(lambda m: "|" * len(m.group(0)), text)
    masked = _TITLES.sub(lambda m: " " * len(m.group(0)), masked)
    found = []
    for match in _NAME.finditer(masked):
        words = match.group(0).split()
        if any(w in _COMPANY_SUFFIXES or w.lower() in _NOT_NAME_WORDS for w in words):
            continue
        if _ORGANISATION_BEFORE.search(masked[:match.start()]):
            continue
        found.append((" ".join(_display(w) for w in words), match.start(), match.end()))
    return found


def _nearest(text: str) -> list[tuple[str, str]]:
    """Each role with the single name closest to it in `text`."""
    names = _names(text)
    pairs = []
    for role in _roles(text):
        if not names:
            break
        name = min(names, key=lambda n: max(n[1] - role.end(), role.start() - n[2]))
        pairs.append((name[0], _canonical(role.group(0))))
    return pairs


def _labelled(text: str) -> list[tuple[str, str]]:
    """Read "label: content" segments, e.g. "Geschäftsführer: A, B" or "CEO: A, CTO: B".

    A role in the label applies to every name of its content. A label without
    a role is only a label: its content is read on its own.
    """
    colons = [i for i, char in enumerate(text) if char == ":"]
    starts = [max(text.rfind(sep, 0, colon) for sep in ",;|:") + 1 for colon in colons]
    pairs = []
    for index, colon in enumerate(colons):
        label = text[starts[index]:colon]
        end = starts[index + 1] - 1 if index + 1 < len(colons) else len(text)
        content = text[colon + 1:end]
        label_roles = _roles(label)
        if label_roles:
            role = _canonical(label_roles[0].group(0))
            pairs += [(name, role) for name, _start, _end in _names(content)]
        else:
            pairs += _nearest(content)
    return pairs


def extract_founders(page: Page) -> list[FoundFounder]:
    """One entry per distinct name found next to a role word, in page order."""
    if page.kind not in _PAGE_KINDS:
        return []
    soup = BeautifulSoup(page.html, "html.parser")
    for tag in soup(_SKIPPED):
        tag.decompose()
    found: dict[str, FoundFounder] = {}
    for block in soup.find_all(_BLOCKS):
        if not _is_leaf(block):
            continue
        text = _text(block)
        roles = _roles(text)
        if not roles:
            continue
        pairs = _labelled(text) if ":" in text else _nearest(text)
        if not pairs and not _names(text):
            # A team card: the role in one block, the name in the next one.
            role = _canonical(roles[0].group(0))
            for sibling in (block.find_previous_sibling(_BLOCKS),
                            block.find_next_sibling(_BLOCKS)):
                if sibling is None or not _is_leaf(sibling) or _roles(_text(sibling)):
                    continue
                names = _names(_text(sibling))
                if names:
                    pairs = [(names[0][0], role)]
                    break
        for name, role in pairs:
            found.setdefault(name, FoundFounder(name, role, page.url))
    return list(found.values())
