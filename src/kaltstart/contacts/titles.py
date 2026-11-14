"""Job titles: which ones are kept, in which category, at which level.

Kept: the people who lead the company, lead one of five functions, or
recruit. Individual contributors, board members, advisors and investors are
not, and neither is a title someone no longer holds.
"""

import re
from dataclasses import dataclass

CATEGORIES = ("leadership", "product", "growth", "data", "operations", "sales",
              "recruiting")
# A student's target role (design spec, section 7.3) and the category it maps to.
ROLE_TO_CATEGORY = {"product": "product", "growth": "growth", "data": "data",
                    "ops": "operations", "bd": "sales"}


@dataclass(frozen=True)
class Title:
    categories: tuple[str, ...]   # in the order of CATEGORIES
    level: str                    # "head" | "manager"


def _words(*alternatives: str) -> re.Pattern:
    """Match any alternative as whole words, whatever the letter case."""
    body = "|".join(alternatives)
    return re.compile(rf"(?<![\w-])(?:{body})(?![\w-])", re.IGNORECASE)


# Never a kept title, whatever else it says.
_NOT_A_TITLE = re.compile(
    r"(?<!\w)(?:assistant|assistenz|assistentin|associate|office|intern|praktikant\w*|"
    r"werkstudent\w*|working student|stagiaire|in residence|data protection|"
    r"datenschutz\w*)(?!\w)", re.IGNORECASE)
# A past job: the part of the title that carries it is dropped, the rest is read.
_PAST = re.compile(r"(?<!\w)(?:ex|former|formerly|ehemalige[rn]?)(?!\w)", re.IGNORECASE)
# "CEO (until 2023)": the whole title is in the past.
_ENDED = re.compile(r"(?<!\w)(?:until|bis)(?!\w)", re.IGNORECASE)
_PARTS = re.compile(r"[,;|()/&]|\s+(?:and|und|et)\s+", re.IGNORECASE)
# The board supervises the company; it does not run it.
_BOARD = re.compile(r"board|verwaltungsrat|aufsichtsrat|beirat|conseil d'administration",
                    re.IGNORECASE)
# Jobs done by one person, not a function led: "Lead Data Scientist" is a
# scientist, whatever "Lead" and "Data" suggest.
_INDIVIDUAL = re.compile(
    r"(?<!\w)(?:engineer(?:in)?|ingenieur(?:in)?|scientist|designer(?:in)?|developer|"
    r"entwickler(?:in)?|analyst(?:in)?|specialist|spezialist(?:in)?|representative|"
    r"generation|architect|consultant|berater(?:in)?|coordinator|trainer(?:in)?|"
    r"training|partner)(?!\w)", re.IGNORECASE)

_FOUNDER_WORDS = (r"co-?founder", "founder", r"mitgründer(?:in)?", r"gründer(?:in)?",
                  r"co-?fondateur", r"co-?fondatrice", "fondateur", "fondatrice")
FOUNDER = _words(*_FOUNDER_WORDS)
_RUNS_THE_COMPANY = (
    *_FOUNDER_WORDS, "chief executive officer", "ceo", "managing director", "coo", "cfo",
    "cto", "chief operating officer", "chief financial officer",
    "chief technology officer", r"geschäftsführ\w*", "geschäftsleitung",
    "directeur général", "directrice générale")
_PRESIDENT = r"(?<!vice )president"
_LEADERSHIP = _words(*_RUNS_THE_COMPANY, _PRESIDENT)
_LEADERSHIP_ON_A_BOARD = _words(*_RUNS_THE_COMPANY)

# The chief officer of a function: both the function and the head level.
_CHIEFS = {
    "product": _words("cpo", "chief product officer"),
    "growth": _words("cmo", "chief marketing officer", "chief growth officer"),
    "data": _words("chief data officer"),
    "sales": _words("cro", "cco", "chief revenue officer", "chief commercial officer"),
    "recruiting": _words("chro", "chief people officer", "chief human resources officer"),
}
_FUNCTIONS = {
    "product": r"product|produkt(?!ion)\w*|produit",
    "growth": r"growth|marketing",
    "data": r"data|analytics|daten",
    "operations": r"operations|betrieb|opérations",
    "sales": r"sales|business development|partnerships?|vertrieb|ventes",
    "recruiting": (r"people|hr|rh|human resources|talent acquisition|talent|recruit\w*|"
                   r"personal|ressources humaines"),
}
# German compounds: "Marketingleiter", "Vertriebsleiterin", "HR-Leiterin".
_COMPOUND_HEADS = {
    "product": r"produkt",
    "growth": r"marketing",
    "operations": r"betriebs?",
    "sales": r"vertriebs?|verkaufs?",
    "recruiting": r"personal|hr-?",
}
_HEAD_WORDS = (r"head|director|vp|vice president|chief|lead|leiter(?:in)?|"
               r"bereichsleiter(?:in)?|abteilungsleiter(?:in)?|directeur|directrice|"
               r"responsable")
_HEAD = _words(_HEAD_WORDS)
_ANY_FUNCTION = "|".join(_FUNCTIONS.values())


def _head_of(category: str) -> re.Pattern:
    """A head word and the function side by side, in either order.

    "Head of Product", "VP Sales EMEA", "Head of Global Sales" (one qualifier
    in between), "Product Lead", "Sales Director", "Marketingleiter". A head
    word and a function word merely present in the same title are not enough.
    """
    function = _FUNCTIONS[category]
    patterns = [
        rf"(?<![\w-])(?:{_HEAD_WORDS})(?:\s+(?:of|for|für|de|des|du|der|the))*"
        rf"(?:\s+[^\s,;|()/&]+)?\s+(?:{function})(?![\w-])",
        rf"(?<![\w-])(?:{function})(?:\s+(?:&|and|und)\s+\S+)?\s+(?:{_HEAD_WORDS})(?![\w-])",
    ]
    if category in _COMPOUND_HEADS:
        patterns.append(rf"(?<![\w-])(?:{_COMPOUND_HEADS[category]})leiter(?:in)?(?![\w-])")
    return re.compile("|".join(patterns), re.IGNORECASE)


def _manager_of(function: str) -> re.Pattern:
    """`<function> manager`, with at most one other function word in between.

    The function must stand right before "manager": this is what keeps
    "Product Manager" and drops "Account Manager" and "Project Manager".
    """
    return re.compile(
        rf"(?<![\w-])(?:{function})(?:\s+(?:{_ANY_FUNCTION}))?\s*-?\s*manager(?:in)?(?![\w-])"
        rf"|(?<![\w-])(?:{_ANY_FUNCTION})\s+(?:{function})\s+manager(?:in)?(?![\w-])",
        re.IGNORECASE)


_HEADS = {category: _head_of(category) for category in _FUNCTIONS}
_MANAGERS = {category: _manager_of(function) for category, function in _FUNCTIONS.items()}
_RECRUITER = _words(r"recruiter(?:in)?")

LEADERSHIP = _LEADERSHIP
# Any word a job title is made of: used to tell a title from a name.
TITLE_WORD = _words(*_RUNS_THE_COMPANY, _PRESIDENT, _HEAD_WORDS, r"manager(?:in)?",
                    _ANY_FUNCTION, r"recruiter(?:in)?",
                    *(rf"(?:{prefix})leiter(?:in)?" for prefix in _COMPOUND_HEADS.values()),
                    *(pattern.pattern for pattern in _CHIEFS.values()))
# German leadership words may be followed directly by the name ("Gründerin Anna Muster").
ROLE_THEN_NAME = _words(r"mitgründer(?:in)?", r"gründer(?:in)?", r"geschäftsführer(?:in)?")


def _present(text: str) -> str:
    """`text` without the parts that speak of a past job."""
    if _ENDED.search(text):
        return ""
    if not _PAST.search(text):
        return text
    return ", ".join(part.strip() for part in _PARTS.split(text)
                     if part.strip() and not _PAST.search(part))


def classify_title(text: str) -> Title | None:
    """The categories and level of a job title, or None when it is not kept."""
    text = _present(" ".join(text.split()))
    if not text or _NOT_A_TITLE.search(text):
        return None
    heads = set()
    managers = set()
    leadership = _LEADERSHIP_ON_A_BOARD if _BOARD.search(text) else _LEADERSHIP
    if leadership.search(text):
        heads.add("leadership")
    if not _INDIVIDUAL.search(text):
        for category in _FUNCTIONS:
            chief = _CHIEFS.get(category)
            if (chief and chief.search(text)) or _HEADS[category].search(text):
                heads.add(category)
            elif _MANAGERS[category].search(text):
                managers.add(category)
        if "recruiting" not in heads and _RECRUITER.search(text):
            managers.add("recruiting")
    kept = heads | managers
    if not kept:
        return None
    return Title(tuple(c for c in CATEGORIES if c in kept), "head" if heads else "manager")
