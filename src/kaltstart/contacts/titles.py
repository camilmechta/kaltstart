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


# A title someone no longer holds, holds for someone else, or a junior one.
_NOT_A_TITLE = re.compile(
    r"(?<!\w)(?:former|ex|ehemalige[rn]?|assistant|assistenz|assistentin|associate|"
    r"office|intern|praktikant\w*|werkstudent\w*|working student|stagiaire)(?!\w)",
    re.IGNORECASE)

FOUNDER = _words(r"co-?founder", "founder", r"mitgründer(?:in)?", r"gründer(?:in)?",
                 r"co-?fondateur", r"co-?fondatrice", "fondateur", "fondatrice")
_LEADERSHIP = _words(
    r"co-?founder", "founder", "chief executive officer", "ceo", "managing director",
    r"(?<!vice )president", "coo", "cfo", "cto", "chief operating officer",
    "chief financial officer", "chief technology officer",
    r"mitgründer(?:in)?", r"gründer(?:in)?", r"geschäftsführer(?:in)?", "geschäftsleitung",
    r"co-?fondateur", r"co-?fondatrice", "fondateur", "fondatrice",
    "directeur général", "directrice générale")

# The chief officer of a function: both the function and the head level.
_CHIEFS = {
    "product": _words("cpo", "chief product officer"),
    "growth": _words("cmo", "chief marketing officer", "chief growth officer"),
    "data": _words("chief data officer"),
    "sales": _words("cro", "cco", "chief revenue officer", "chief commercial officer"),
    "recruiting": _words("chro", "chief people officer", "chief human resources officer"),
}
_FUNCTIONS = {
    "product": r"product|produkt\w*|produit",
    "growth": r"growth|marketing",
    "data": r"data|analytics",
    "operations": r"operations|betrieb|opérations",
    "sales": r"sales|business development|partnerships|vertrieb\w*|ventes",
    "recruiting": (r"people|hr|human resources|talent acquisition|talent|recruiting|"
                   r"personal|ressources humaines"),
}
_HEAD = _words("head", "director", "vp", "vice president", "chief", "lead",
               r"\w*leiter(?:in)?", "directeur", "directrice", "responsable")
_ANY_FUNCTION = "|".join(_FUNCTIONS.values())


def _manager_of(function: str) -> re.Pattern:
    """`<function> manager`, with at most one other function word in between.

    The function must stand right before "manager": this is what keeps
    "Product Manager" and drops "Account Manager" and "Project Manager".
    """
    return re.compile(
        rf"(?<![\w-])(?:{function})(?:\s+(?:{_ANY_FUNCTION}))?\s*-?\s*manager(?:in)?(?![\w-])"
        rf"|(?<![\w-])(?:{_ANY_FUNCTION})\s+(?:{function})\s+manager(?:in)?(?![\w-])",
        re.IGNORECASE)


LEADERSHIP = _LEADERSHIP
# Any word a job title is made of: used to tell a title from a name.
TITLE_WORD = _words(_LEADERSHIP.pattern, _HEAD.pattern, r"manager(?:in)?", _ANY_FUNCTION,
                    *(pattern.pattern for pattern in _CHIEFS.values()))
# German leadership words may be followed directly by the name ("Gründerin Anna Muster").
ROLE_THEN_NAME = _words(r"mitgründer(?:in)?", r"gründer(?:in)?", r"geschäftsführer(?:in)?")

_MANAGERS = {category: _manager_of(function) for category, function in _FUNCTIONS.items()}
_FUNCTION_WORDS = {category: _words(function) for category, function in _FUNCTIONS.items()}


def classify_title(text: str) -> Title | None:
    """The categories and level of a job title, or None when it is not kept."""
    text = " ".join(text.split())
    if not text or _NOT_A_TITLE.search(text):
        return None
    heads = set()
    managers = set()
    if _LEADERSHIP.search(text):
        heads.add("leadership")
    has_head_word = bool(_HEAD.search(text))
    for category in _FUNCTIONS:
        chief = _CHIEFS.get(category)
        if (chief and chief.search(text)) or (
                has_head_word and _FUNCTION_WORDS[category].search(text)):
            heads.add(category)
        elif _MANAGERS[category].search(text):
            managers.add(category)
    kept = heads | managers
    if not kept:
        return None
    return Title(tuple(c for c in CATEGORIES if c in kept), "head" if heads else "manager")
