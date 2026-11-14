"""People a company presents with their job title, on home, legal and team pages.

Four measurements on real sites shaped these rules. A person is accepted only
in one of the layouts sites actually use:

- a card: one block holding nothing but the name, next to a short block
  holding the title, or next to one of that block's wrappers;
- a line: "Name, title" or "Name - title";
- a label: "Geschäftsführer: Name, Name".

Running prose is never read, and neither is a card that sits with a quotation
(a customer testimonial). A title tied to another organisation is not this
company's. When in doubt nothing is returned: a wrong name ends up in a mail.
"""

import re

from bs4 import BeautifulSoup, Tag

from kaltstart.contacts.models import FoundPerson, Page
from kaltstart.contacts.titles import (
    LEADERSHIP, ROLE_THEN_NAME, TITLE_WORD, Title, classify_title)

_PAGE_KINDS = ("home", "legal", "team")
_BLOCKS = ("p", "li", "td", "th", "div", "span", "dd", "dt",
           "h1", "h2", "h3", "h4", "h5", "h6")
_SKIPPED = ("script", "style", "noscript", "nav", "header")
MAX_TITLE_BLOCK_WORDS = 14    # longer blocks are prose
MAX_NAME_BLOCK_WORDS = 8
MAX_LEVELS_UP = 3             # how far above the title a name block may sit
# A customer testimonial looks like a team card: a name, then "CEO". What
# gives it away is the quotation it sits with.
MAX_TESTIMONIAL_WORDS = 120
_QUOTE_MARKS = re.compile("[“”„«»]")
# A biography may put a few words in quotation marks: an award, a nickname.
MIN_QUOTED_WORDS = 8
# A testimonial without quotation marks is signed with the customer's logo.
_LOGO = re.compile(r"logo", re.IGNORECASE)
# Text a site keeps in the page and never shows: a field its page builder left
# out for this entry. The `hidden` attribute is not in this list on purpose:
# it marks what sits behind a tab or a filter, which a visitor can open.
_HIDDEN_CLASS = frozenset(("w-condition-invisible",))
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none", re.IGNORECASE)
_TESTIMONIAL_CLASS = re.compile(r"testimonial|quote|review|kundenstimme|referenz", re.IGNORECASE)
# A job opening also looks like a team card: a title, then "Full Time".
_JOB_AD_TITLE = re.compile(r"\((?:[mwfdx]\s*/\s*){1,3}[mwfdx]\)|\d\s*%", re.IGNORECASE)
# Matched against each class or id, whole or between hyphens and underscores.
# "position" and "job-title" are left out on purpose: team cards use them for
# a person's own title.
_JOB_AD_CLASS = re.compile(
    r"(?:^|[-_])(?:jobs|vacanc\w*|openings?|careers?|karriere|stellen\w*|offres?|hiring|"
    r"job[-_]?(?:listing|offer|posting|opening|ad|card|item|list|board)s?)(?:$|[-_])|^job$",
    re.IGNORECASE)
# Sections of a page that show people or titles who are not the team.
_NOT_THE_TEAM = re.compile(
    r"(?<!\w)(?:advisor\w*|advisory|board|investor\w*|backers?|verwaltungsrat|beirat|"
    r"aufsichtsrat|positions?|jobs|careers?|karriere|stellen|vacanc\w*|hiring|"
    r"customers?|kunden|testimonials?|stories|speakers?|webinar\w*|press|news)(?!\w)",
    re.IGNORECASE)
_HEADINGS = ("h1", "h2", "h3", "h4")
_ALL_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
# Small words a title may contain in lower case; any other lower-case word
# means the block is a sentence ("Built for every Head of Sales").
_CONNECTORS = frozenset(("of", "and", "und", "der", "die", "das", "des", "de", "du", "la",
                         "le", "et", "für", "for", "the", "at", "bei", "von", "in", "co"))

_ACADEMIC = re.compile(r"\b(?:Dr|Prof|Mag|Ing|Dipl\.-Ing)\b\.?", re.IGNORECASE)
_CREDENTIAL = r"(?:E?MBA|Ph\.?D\.?|M\.?Sc\.?|B\.?Sc\.?|MRICS|CFA)"
_TRAILING_CREDENTIALS = re.compile(rf"(?:,\s*(?:{_CREDENTIAL}|[A-Z]{{2,6}}))+\s*$")
_LEADING_CREDENTIALS = re.compile(rf"^(?:[\s,|–—-]*{_CREDENTIAL}(?![\w.]))+")
_WORD = r"[A-ZÀ-ÖØ-Þ][^\W\d_]*(?:[-'’][^\W\d_]+)*"
_PARTICLE = r"(?:von|van|de|del|di|der|den)"
_NAME = rf"{_WORD}(?:\s+(?:{_PARTICLE}\s+)*{_WORD}){{1,3}}"
_WHOLE_NAME = re.compile(rf"^{_NAME}$")
_LEADING_NAME = re.compile(rf"^({_NAME})\s*(,|-|–|—|\||\()")
_NAME_SEPARATORS = re.compile(r"\s+(?:und|and|&)\s+|\s*[,/]\s*")
_CAPITALISED = re.compile(r"[A-ZÀ-ÖØ-Þ][\w'’.-]*")
_ELSEWHERE = re.compile(r"(?:\bat\b|@|\bbei\b|\bchez\b)\s*((?:[A-ZÀ-ÖØ-Þ][\w'’.-]*\s*){1,4})")
_COMPANY_SUFFIXES = frozenset(("ag", "gmbh", "sa", "sàrl", "sarl", "ltd", "inc", "kg",
                               "ug", "se", "llc"))
# Words of job titles and of organisations: never part of a person's name,
# and not an organisation's name when they stand in a title ("CEO & CTO").
_VOCABULARY = frozenset((
    "chief", "officer", "executive", "technology", "technical", "operating",
    "financial", "finance", "commercial", "scientific", "science", "product",
    "marketing", "sales", "business", "operations", "research", "development",
    "innovation", "strategy", "people", "talent", "management", "manager",
    "owner", "lead", "leader", "head", "director", "president", "vp", "svp",
    "senior", "sr", "junior", "jr", "former", "interim", "deputy", "acting",
    "engineer", "engineering", "investment", "culture", "growth", "data",
    "professor", "advisor", "adviser", "investor", "angel", "partner", "board",
    "member", "chairman", "chairwoman", "chair", "entrepreneur", "associate",
    "ceo", "cto", "cfo", "coo", "cco", "cso", "cio", "cmo", "cpo", "cro", "mba",
    "and", "und", "the", "of", "at", "bei", "der", "die", "das", "co",
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
    # job openings, places and page labels that sit where a name would
    "full", "part", "time", "remote", "hybrid", "apply", "now", "permanent",
    "position", "positions", "open", "vollzeit", "teilzeit", "festanstellung",
    "praktikum", "new", "smart", "customer", "customers", "stories", "case",
    "study", "studies", "learn", "get", "started", "book", "demo", "request",
    "sign", "press", "news", "blog", "products", "services", "features",
    "pricing", "privacy", "policy", "terms", "jobs", "careers", "job",
    "switzerland", "schweiz", "suisse", "germany", "deutschland", "austria",
    "österreich", "europe", "europa", "zurich", "zürich", "basel", "bern",
    "geneva", "genf", "genève", "lausanne", "lugano", "zug", "berlin",
    "munich", "münchen", "vienna", "wien", "hamburg", "london", "paris",
    "york", "stadt", "region", "developer", "designer", "analyst", "scientist",
    "specialist", "consultant", "student",
    # job titles in Italian and French, read on pages that list who a product is for
    "direttore", "direttrice", "responsabile", "amministratore", "amministrativo",
    "delegato", "generale", "finanziario", "commerciale", "vendite", "personale",
    "directeur", "directrice", "général", "générale", "gérant", "gérante",
    "leiter", "leiterin",
))


def _text(element: Tag) -> str:
    return " ".join(element.get_text(" ").replace("​", "").split())


def _is_leaf(element: Tag) -> bool:
    return element.find(_BLOCKS) is None


def _squash(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.lower())


def _company_key(company_name: str | None) -> str:
    words = [w for w in re.findall(r"[^\W_]+", (company_name or "").lower())
             if w not in _COMPANY_SUFFIXES]
    return "".join(words)


def _organisation(words: list[str]) -> list[str]:
    return [w for w in words if w.lower().strip(".") not in _VOCABULARY]


def _is_this_company(words: list[str], company_key: str) -> bool:
    named = _squash(" ".join(_organisation(words)))
    return bool(company_key) and (
        company_key in _squash(" ".join(words)) or (len(named) >= 3 and named in company_key))


def _capitalised(text: str) -> list[str]:
    return [w for w in _CAPITALISED.findall(TITLE_WORD.sub(" ", text))
            if w.lower() not in _COMPANY_SUFFIXES]


def _only_an_organisation(clause: str) -> list[str]:
    """The words of `clause` when it is nothing but an organisation's name."""
    words = [w for w in clause.split() if w not in ("&", "-")]
    names = _capitalised(clause)
    if names and len(words) <= 4 and len(_organisation(names)) == len(words) \
            and not TITLE_WORD.search(clause):
        return names
    return []


def _leader_elsewhere(text: str, role: re.Match, company_key: str) -> bool:
    """True when a leadership word is tied to another organisation's name:
    right after it ("CEO Other Group"), right before it ("Otherix CEO"), or
    alone after a comma ("CEO, Othergem")."""
    after = text[role.end():]
    split = re.search(r"[,;|()]", after)
    clause = after[:split.start()] if split else after
    if ROLE_THEN_NAME.fullmatch(role.group(0)) and _whole_names(clause, company_key):
        return False
    words = _capitalised(clause)
    if _organisation(words):
        return not _is_this_company(words, company_key)
    before = re.split(r"[,;|()&/:-]", text[:role.start()])[-1].split()
    if before and _CAPITALISED.fullmatch(before[-1]) and _organisation(before[-1:]):
        return not _is_this_company(before[-1:], company_key)
    if split and split.group(0) == ",":
        following = re.split(r"[,;|()]", after[split.end():], maxsplit=1)[0]
        names = _only_an_organisation(following)
        if names:
            return not _is_this_company(names, company_key)
    return False


def _held_elsewhere(text: str, company_key: str) -> bool:
    """True when the title belongs to another organisation than this company."""
    if any(_leader_elsewhere(text, role, company_key) for role in LEADERSHIP.finditer(text)):
        return True
    for match in _ELSEWHERE.finditer(text):          # "Head of Product at Other Works"
        names = _capitalised(match.group(1))
        if _organisation(names) and not _is_this_company(names, company_key):
            return True
    for clause in text.split(",")[1:]:               # "Head of Product, Other Works"
        names = _only_an_organisation(clause)
        if names and not _is_this_company(names, company_key):
            return True
    return False


def _own_title(text: str, company_key: str) -> Title | None:
    """The classified title, when it is a kept one held at this company."""
    title = classify_title(text)
    if title is None or _held_elsewhere(text, company_key):
        return None
    return title


def _display(word: str) -> str:
    return word.capitalize() if len(word) > 1 and word.isupper() else word


def _person(candidate: str, company_key: str) -> str | None:
    """`candidate` as a displayable name, or None when it is not a person's."""
    words = candidate.split()
    if TITLE_WORD.search(candidate):
        return None
    if any(w.lower().strip(".") in _VOCABULARY or w.lower() in _COMPANY_SUFFIXES
           for w in words):
        return None
    if company_key and (company_key in _squash(candidate)
                        or _squash(candidate) in company_key):
        return None
    return " ".join(_display(w) for w in words)


def _without_academic_titles(text: str) -> str:
    return " ".join(_ACADEMIC.sub(" ", text).split())


def _whole_names(text: str, company_key: str) -> list[str]:
    """The names, when `text` holds nothing but one or several names."""
    cleaned = _TRAILING_CREDENTIALS.sub("", _without_academic_titles(text)).strip()
    names = []
    for piece in _NAME_SEPARATORS.split(cleaned):
        if not _WHOLE_NAME.match(piece):
            return []
        name = _person(piece, company_key)
        if name is None:
            return []
        names.append(name)
    return names


Found = tuple[str, str, Title]    # name, title text, classified title


def _line(text: str, company_key: str) -> list[Found]:
    """ "Name, title" or "Name - title": the name a line starts with."""
    cleaned = _without_academic_titles(text)
    match = _LEADING_NAME.match(cleaned)
    if not match:
        return []
    name = _person(match.group(1), company_key)
    rest = cleaned[match.end():]
    if match.group(2) == "(":
        rest = rest.split(")", 1)[0]
    rest = _LEADING_CREDENTIALS.sub("", rest).strip(" ,|–—-")
    title = _own_title(rest, company_key)
    return [(name, rest, title)] if name and title else []


def _title_then_name(text: str, company_key: str) -> list[Found]:
    """ "Gründerin Anna Muster": a German title, then nothing but the name."""
    first = ROLE_THEN_NAME.match(text)
    title = _own_title(first.group(0), company_key) if first else None
    if not title:
        return []
    return [(name, first.group(0), title)
            for name in _whole_names(text[first.end():], company_key)]


def _labelled(text: str, company_key: str) -> list[Found]:
    """Read "label: content" segments, e.g. "Geschäftsführer: A, B" or "CEO: A, CTO: B".

    A title in the label applies to every name of its content. A label without
    a title is only a label: its content is read as a line of its own.
    """
    colons = [i for i, char in enumerate(text) if char == ":"]
    starts = [max(text.rfind(sep, 0, colon) for sep in ",;|:") + 1 for colon in colons]
    found: list[Found] = []
    for index, colon in enumerate(colons):
        label = text[starts[index]:colon].split("/")[-1].strip()
        end = starts[index + 1] - 1 if index + 1 < len(colons) else len(text)
        content = text[colon + 1:end].strip()
        title = _own_title(label, company_key)
        if title:
            found += [(name, label, title) for name in _whole_names(content, company_key)]
        elif ":" not in content:
            found += _in_block(content, company_key)
    return found


def _in_block(text: str, company_key: str) -> list[Found]:
    """People a short block states by itself."""
    if ":" in text:
        return _labelled(text, company_key)
    return _line(text, company_key) or _title_then_name(text, company_key)


def _nearest_filled(node: Tag, direction: str) -> Tag | None:
    """The closest sibling that has text; empty ones (pictures) are skipped."""
    siblings = (node.find_previous_siblings(True) if direction == "previous"
                else node.find_next_siblings(True))
    return next((sibling for sibling in siblings[:3] if _text(sibling)), None)


def _neighbour_names(block: Tag, company_key: str) -> list[str]:
    """Names in the block right before the title: the team-card layout.

    The name block is the title's own neighbour, or the neighbour of one of
    the title's wrappers. It comes before the title: a title above a block of
    text is a job opening or a heading, not a person. Its text is nothing
    but the name: a neighbouring card with a name and a job is not a name.
    """
    node = block
    for _level in range(MAX_LEVELS_UP + 1):
        sibling = _nearest_filled(node, "previous")
        if sibling is not None:
            text = _text(sibling)
            if len(text.split()) <= MAX_NAME_BLOCK_WORDS and not TITLE_WORD.search(text):
                names = _whole_names(text, company_key)
                if names:
                    return names
        if node.parent is None:
            break
        node = node.parent
    # Some cards write the title first. Only the title's own next neighbour is
    # looked at, and never under a heading: a heading that is a title announces
    # a job opening or a section.
    if block.name not in _ALL_HEADINGS:
        sibling = _nearest_filled(block, "next")
        if sibling is not None and _is_leaf(sibling):
            text = _text(sibling)
            if len(text.split()) <= MAX_NAME_BLOCK_WORDS and not TITLE_WORD.search(text):
                return _whole_names(text, company_key)
    return []


def _is_job_opening(block: Tag, text: str) -> bool:
    if _JOB_AD_TITLE.search(text):
        return True
    return any(_JOB_AD_CLASS.search(token)
               for node in [block, *list(block.parents)[:5]]
               for token in [*node.get("class", []), node.get("id") or ""])


def _reads_like_a_title(text: str, company_key: str) -> bool:
    """False for a sentence: a title has no lower-case word but small connectors."""
    for word in re.findall(r"[^\W\d_]+", text):
        if word[0].islower() and word not in _CONNECTORS \
                and word not in _VOCABULARY and not TITLE_WORD.fullmatch(word) \
                and not (company_key and word in company_key):
            return False
    return True


def _outside_the_team(block: Tag, company_key: str) -> bool:
    """True when the nearest section heading announces advisors, a board,
    investors, job openings or customers. A heading that is itself somebody's
    name (a team card's own heading) is passed over."""
    for heading in block.find_all_previous(_HEADINGS, limit=6):
        text = _text(heading)
        if _NOT_THE_TEAM.search(text):
            return True
        if text and not _whole_names(text, company_key):
            return False
    return False


def _in_testimonial(block: Tag) -> bool:
    """True when the block sits with a quotation: a customer speaking, not the team."""
    logo_seen = False
    for ancestor in list(block.parents)[:5]:
        if ancestor.name in ("blockquote", "q"):
            return True
        marked = " ".join([*ancestor.get("class", []), ancestor.get("id") or ""])
        if _TESTIMONIAL_CLASS.search(marked):
            return True
        text = _text(ancestor)
        if len(text.split()) > MAX_TESTIMONIAL_WORDS:
            return False
        if ancestor.find(["blockquote", "q"]) or _quotes_somebody(text):
            return True
        if not logo_seen and _has_logo(ancestor):
            # Judged once, on the smallest wrapper that holds the logo.
            logo_seen = True
            if _holds_a_statement(ancestor):
                return True
    return False


def _has_logo(card: Tag) -> bool:
    return any(_LOGO.search(" ".join([image.get("alt") or "", *image.get("class", [])]))
               for image in card.find_all("img"))


def _holds_a_statement(card: Tag) -> bool:
    """True when the card holds a sentence: with a logo, a customer speaking."""
    return any(_is_leaf(block) and len(_text(block).split()) >= MIN_QUOTED_WORDS
               for block in card.find_all(_BLOCKS))


def _quotes_somebody(text: str) -> bool:
    """True when quotation marks hold a statement, not just a few words."""
    pieces = _QUOTE_MARKS.split(text)
    quoted = pieces[1:-1] if len(pieces) > 2 else pieces[1:]
    return any(len(piece.split()) >= MIN_QUOTED_WORDS for piece in quoted)


def _is_hidden(tag: Tag) -> bool:
    if _HIDDEN_STYLE.search(tag.get("style") or ""):
        return True
    return any(token in _HIDDEN_CLASS for token in tag.get("class", []))


def _first_line(block: Tag) -> str:
    """The text before the block's first line break, when it has one."""
    for line_break in block.find_all("br"):
        line_break.replace_with("\n")
    lines = [" ".join(line.split()) for line in block.get_text(" ").replace("\u200b", "").split("\n")]
    lines = [line for line in lines if line]
    return lines[0] if len(lines) > 1 else ""


def extract_people(page: Page, company_name: str | None = None) -> list[FoundPerson]:
    """One entry per distinct name stated with a kept title at this company."""
    if page.kind not in _PAGE_KINDS:
        return []
    company_key = _company_key(company_name)
    soup = BeautifulSoup(page.html, "html.parser")
    for tag in soup(_SKIPPED):
        tag.decompose()
    for tag in [tag for tag in soup.find_all(True) if _is_hidden(tag)]:
        if not tag.decomposed:
            tag.decompose()
    people: dict[str, FoundPerson] = {}
    for block in soup.find_all(_BLOCKS):
        if not _is_leaf(block):
            continue
        text = _text(block)
        if not TITLE_WORD.search(text):
            continue
        first_line = _first_line(block)
        if len(text.split()) > MAX_TITLE_BLOCK_WORDS:
            # Prose, unless the title stands alone on the block's first line.
            if not first_line or len(first_line.split()) > MAX_TITLE_BLOCK_WORDS:
                continue
            text = first_line
        if _in_testimonial(block) or _is_job_opening(block, text):
            continue
        found = _in_block(text, company_key)
        if not found and ":" not in text:
            # A card's title, or the first line of a block that goes on with a biography.
            for candidate in (text, first_line):
                if not candidate or not TITLE_WORD.search(candidate) \
                        or not _reads_like_a_title(candidate, company_key):
                    continue
                title = _own_title(candidate, company_key)
                if title:
                    found = [(name, candidate, title)
                             for name in _neighbour_names(block, company_key)]
                    break
        if found and _outside_the_team(block, company_key):
            continue
        for name, title_text, title in found:
            people.setdefault(name, FoundPerson(
                name, title_text, title.categories, title.level, page.url))
    return list(people.values())
