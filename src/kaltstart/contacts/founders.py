"""Founder names on home, legal-notice and team pages.

The first measurement on real sites showed where a looser reading goes wrong:
job titles and organisations taken for people, and founders of other
companies taken for this company's. A name is therefore accepted only in one
of the layouts sites actually use, and only when the role is held at this
company:

- a card: one block holding nothing but the name, next to a short block
  holding the role;
- a line: "Name, role" or "Name - role";
- a label: "Geschäftsführer: Name, Name".

Running prose is never read. When in doubt nothing is returned, because a
wrong name ends up in a mail.
"""

import re

from bs4 import BeautifulSoup, Tag

from kaltstart.contacts.models import FoundFounder, Page

# In priority order: a founder role is preferred to "CEO" when a block has both.
ROLE_WORDS: tuple[str, ...] = (
    "Co-Founder", "Cofounder", "Founder", "Chief Executive Officer", "CEO",
    "Managing Director", "Mitgründerin", "Mitgründer", "Gründerin", "Gründer",
    "Geschäftsführerin", "Geschäftsführer", "Geschäftsleitung",
)
_PAGE_KINDS = ("home", "legal", "team")
_BLOCKS = ("p", "li", "td", "th", "div", "span", "dd", "dt",
           "h1", "h2", "h3", "h4", "h5", "h6")
_SKIPPED = ("script", "style", "noscript", "nav", "header", "blockquote")
MAX_ROLE_BLOCK_WORDS = 14     # longer blocks are prose
MAX_NAME_BLOCK_WORDS = 8

_ROLE = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(r) for r in ROLE_WORDS) + r")(?![\w-])",
    re.IGNORECASE)
# "Former CEO", "Head of CEO Office", "Founder Associate" are not the role.
_NOT_A_ROLE_BEFORE = re.compile(
    r"(?:former|ex|ehemaliger|ehemalige|head of|assistant to(?: the)?)[\s-]*$",
    re.IGNORECASE)
_NOT_A_ROLE_AFTER = re.compile(
    r"^\s*(?:associate|office|assistant|in residence)\b", re.IGNORECASE)

_TITLES = re.compile(r"\b(?:Dr|Prof|Mag|Ing|Dipl\.-Ing)\b\.?", re.IGNORECASE)
_CREDENTIALS = re.compile(r"(?:,\s*(?:[A-Z]{2,6}|Ph\.?D\.?|M\.?Sc\.?))+\s*$")
_WORD = r"[A-ZÀ-ÖØ-Þ][^\W\d_]*(?:[-'’][^\W\d_]+)*"
_PARTICLE = r"(?:von|van|de|del|di|der|den)"
_NAME = rf"{_WORD}(?:\s+(?:{_PARTICLE}\s+)*{_WORD}){{1,3}}"
_WHOLE_NAME = re.compile(rf"^{_NAME}$")
_LEADING_NAME = re.compile(rf"^({_NAME})\s*(?:,|-|–|—|\||\()")
_NAME_SEPARATORS = re.compile(r"\s+(?:und|and|&)\s+|\s*[,/]\s*")
_CAPITALISED = re.compile(r"[A-ZÀ-ÖØ-Þ][\w'’.-]*")
_COMPANY_SUFFIXES = frozenset(("ag", "gmbh", "sa", "sàrl", "sarl", "ltd", "inc", "kg",
                               "ug", "se", "llc"))
# Words of job titles and of organisations: never part of a person's name,
# and not an organisation when they follow a role ("CEO & CTO").
_VOCABULARY = frozenset((
    "chief", "officer", "executive", "technology", "technical", "operating",
    "financial", "finance", "commercial", "scientific", "science", "product",
    "marketing", "sales", "business", "operations", "research", "development",
    "innovation", "strategy", "people", "talent", "management", "manager",
    "owner", "lead", "leader", "head", "director", "president", "vp", "svp",
    "senior", "sr", "junior", "jr", "former", "engineer", "engineering",
    "professor", "advisor", "adviser", "investor", "angel", "partner", "board",
    "member", "chairman", "chairwoman", "chair", "entrepreneur", "associate",
    "ceo", "cto", "cfo", "coo", "cco", "cso", "cio", "cmo", "cpo", "cro", "mba",
    "and", "und", "the", "of", "at", "bei", "der", "die", "das",
    # organisations
    "group", "capital", "ventures", "venture", "partners", "institute",
    "academy", "university", "universität", "labs", "lab", "software",
    "systems", "solutions", "technologies", "robotics", "foundation", "fund",
    "expo", "company", "holding", "holdings", "association", "school",
    # page furniture
    "about", "us", "our", "from", "dear", "friends", "message", "story",
    "team", "award", "collective", "office", "year", "contact", "home", "meet",
    "welcome", "read", "more", "person", "stelle", "unser", "unsere", "über",
    "uns", "mehr", "kontakt", "impressum",
))


def _text(element: Tag) -> str:
    return " ".join(element.get_text(" ").split())


def _is_leaf(element: Tag) -> bool:
    return element.find(_BLOCKS) is None


def _squash(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.lower())


def _company_key(company_name: str | None) -> str:
    words = [w for w in re.findall(r"[^\W_]+", (company_name or "").lower())
             if w not in _COMPANY_SUFFIXES]
    return "".join(words)


# In German the name may follow the role directly ("Geschäftsführer Anna
# Muster"). In English it does not, so capitalised words after an English
# role name an organisation ("CEO Other Group").
_ROLE_THEN_NAME = frozenset(r.lower() for r in ROLE_WORDS
                            if r[0] in "GM" and r != "Managing Director")


def _held_here(text: str, role: re.Match, company_key: str) -> bool:
    """False when the role is followed by the name of another organisation."""
    clause = re.split(r"[,;|()]", text[role.end():], maxsplit=1)[0]
    if role.group(0).lower() in _ROLE_THEN_NAME and _whole_names(clause, company_key):
        return True
    capitalised = [w for w in _CAPITALISED.findall(_ROLE.sub(" ", clause))
                   if w.lower() not in _COMPANY_SUFFIXES]
    organisation = [w for w in capitalised if w.lower().strip(".") not in _VOCABULARY]
    if not organisation:
        return True
    if not company_key:
        return False
    named = _squash(" ".join(organisation))
    return company_key in _squash(" ".join(capitalised)) or (
        len(named) >= 3 and named in company_key)


def _own_role(text: str, company_key: str) -> str | None:
    """The founder role this text gives someone at this company, if any."""
    held = set()
    for match in _ROLE.finditer(text):
        if _NOT_A_ROLE_BEFORE.search(text[:match.start()]):
            continue
        if _NOT_A_ROLE_AFTER.match(text[match.end():]):
            continue
        if _held_here(text, match, company_key):
            held.add(match.group(0).lower())
    return next((r for r in ROLE_WORDS if r.lower() in held), None)


def _display(word: str) -> str:
    return word.capitalize() if len(word) > 1 and word.isupper() else word


def _person(candidate: str, company_key: str) -> str | None:
    """`candidate` as a displayable name, or None when it is not a person's."""
    words = candidate.split()
    if any(w.lower().strip(".") in _VOCABULARY or w.lower() in _COMPANY_SUFFIXES
           for w in words):
        return None
    if company_key and (company_key in _squash(candidate)
                        or _squash(candidate) in company_key):
        return None
    return " ".join(_display(w) for w in words)


def _clean(text: str) -> str:
    """Drop academic titles and credentials: "Dr Anna Muster, MBA" -> "Anna Muster"."""
    return _CREDENTIALS.sub("", " ".join(_TITLES.sub(" ", text).split())).strip()


def _whole_names(text: str, company_key: str) -> list[str]:
    """The names, when `text` holds nothing but one or several names."""
    names = []
    for piece in _NAME_SEPARATORS.split(_clean(text)):
        if not _WHOLE_NAME.match(piece):
            return []
        name = _person(piece, company_key)
        if name is None:
            return []
        names.append(name)
    return names


def _leading_name(text: str, company_key: str) -> list[str]:
    """The name a line starts with: "Name, role" or "Name - role"."""
    match = _LEADING_NAME.match(_clean(_ROLE.sub("|", text)))
    name = _person(match.group(1), company_key) if match else None
    return [name] if name else []


def _names_in_block(text: str, company_key: str) -> list[tuple[str, str]]:
    """`(name, role)` pairs a short block states by itself."""
    if ":" in text:
        return _labelled(text, company_key)
    role = _own_role(text, company_key)
    if role is None:
        return []
    names = _leading_name(text, company_key)
    if not names:
        # "Gründerin Anna Muster": the role, then nothing but the name.
        first = _ROLE.match(text)
        if first:
            names = _whole_names(text[first.end():], company_key)
    return [(name, role) for name in names]


def _labelled(text: str, company_key: str) -> list[tuple[str, str]]:
    """Read "label: content" segments, e.g. "Geschäftsführer: A, B" or "CEO: A, CTO: B".

    A role in the label applies to every name of its content. A label without
    a role is only a label: its content is read as a line of its own.
    """
    colons = [i for i, char in enumerate(text) if char == ":"]
    starts = [max(text.rfind(sep, 0, colon) for sep in ",;|:") + 1 for colon in colons]
    pairs = []
    for index, colon in enumerate(colons):
        label = text[starts[index]:colon]
        end = starts[index + 1] - 1 if index + 1 < len(colons) else len(text)
        content = text[colon + 1:end].strip()
        role = _own_role(label, company_key)
        if role:
            pairs += [(name, role) for name in _whole_names(content, company_key)]
        else:
            pairs += _names_in_block(content, company_key) if ":" not in content else []
    return pairs


def _neighbour_names(block: Tag, company_key: str) -> list[str]:
    """Names in the block right before, else right after: the team-card layout."""
    for sibling in (block.find_previous_sibling(True), block.find_next_sibling(True)):
        if sibling is None:
            continue
        text = _text(sibling)
        if not text or len(text.split()) > MAX_NAME_BLOCK_WORDS or _ROLE.search(text):
            continue
        names = _whole_names(text, company_key)
        if names:
            return names
    return []


def extract_founders(page: Page, company_name: str | None = None) -> list[FoundFounder]:
    """One entry per distinct name stated with a founder role at this company."""
    if page.kind not in _PAGE_KINDS:
        return []
    company_key = _company_key(company_name)
    soup = BeautifulSoup(page.html, "html.parser")
    for tag in soup(_SKIPPED):
        tag.decompose()
    found: dict[str, FoundFounder] = {}
    for block in soup.find_all(_BLOCKS):
        if not _is_leaf(block):
            continue
        text = _text(block)
        if not _ROLE.search(text) or len(text.split()) > MAX_ROLE_BLOCK_WORDS:
            continue
        pairs = _names_in_block(text, company_key)
        if not pairs and ":" not in text:
            role = _own_role(text, company_key)
            if role:
                pairs = [(name, role) for name in _neighbour_names(block, company_key)]
        for name, role in pairs:
            found.setdefault(name, FoundFounder(name, role, page.url))
    return list(found.values())
