"""Whether a name read on a company's site is a person's, and its clean form.

Used by the scraper before storing a person and by the web app before showing
one, so that names already stored are cleaned at once (decision D84)."""

import re

# Degrees, academic titles and schools written before or after a name.
_BEFORE = frozenset((
    "msc", "m.sc", "m.sc.", "bsc", "b.sc", "b.sc.", "ma", "m.a.", "ba", "b.a.", "mba", "emba",
    "phd", "ph.d.", "dr", "dr.", "med", "med.", "rer", "rer.", "nat", "nat.", "prof", "prof.",
    "mag", "mag.", "ing", "ing.", "dipl.-ing.", "dipl.-ing", "dipl.", "lic", "lic.", "mas",
    "cas", "mlaw", "blaw", "llm", "ll.m.", "eth", "epfl", "hsg", "uzh", "tum", "lmu", "wu",
    "kit", "rwth", "fh", "hes", "zhaw",
))
_AFTER = re.compile(r"(?:\s*,\s*(?:E?MBA|Ph\.?D\.?|M\.?Sc\.?|B\.?Sc\.?|LL\.?M\.?|MRICS|CFA|"
                    r"[A-Z]{2,5}))+\s*$")
# Words that start a sentence or a heading, never a name.
_NOT_A_NAME = frozenset((
    "was", "wie", "wer", "wo", "warum", "wir", "unser", "unsere", "ihr", "ihre", "sie", "das",
    "die", "der", "und", "oder", "mit", "für", "über", "mehr", "alle", "neu", "jetzt",
    "what", "how", "who", "why", "where", "we", "our", "your", "the", "and", "with", "for",
    "about", "more", "all", "new", "now", "meet", "join", "team", "kontakt", "contact",
))
_PARTICLES = frozenset(("von", "van", "de", "del", "della", "di", "da", "dos", "der", "den",
                        "du", "la", "le", "zu", "ter", "ten", "af", "y"))
_WORD = re.compile(r"^[A-ZÀ-ÖØ-Þ][^\W\d_]*(?:[-'’][^\W\d_]+)*$")


def clean_name(raw: str | None) -> str | None:
    """The person's name without degrees or schools, or None when `raw` does
    not read as a person's name (a sentence, a heading, a single word)."""
    if not raw:
        return None
    text = _AFTER.sub("", " ".join(raw.split()))
    if not text or text[-1] in ".?!:;":
        return None
    words = text.split()
    while words and words[0].lower().rstrip(",") in _BEFORE:
        words.pop(0)
    if not 2 <= len(words) <= 5:
        return None
    for index, word in enumerate(words):
        lower = word.lower()
        if index and lower in _PARTICLES:       # "von der" inside a name
            continue
        if lower in _NOT_A_NAME:
            return None
        if not _WORD.match(word):
            return None
    if words[-1].lower() in _PARTICLES:
        return None
    return " ".join(words)


# The most common German titles, with their meaning for a student who reads
# no German. The title itself is always shown as the company wrote it.
_TITLE_HINTS = (
    (re.compile(r"mitgründer|mitbegründer|co-gründer", re.I), "Co-founder"),
    (re.compile(r"(?<!mit)(?<!co-)gründer", re.I), "Founder"),
    (re.compile(r"geschäftsführ", re.I), "Managing director"),
    (re.compile(r"vorstandsvorsitz", re.I), "Chair of the board"),
    (re.compile(r"\bvorstand", re.I), "Board member"),
    (re.compile(r"inhaber", re.I), "Owner"),
    (re.compile(r"gesellschafter", re.I), "Shareholder"),
    (re.compile(r"prokurist", re.I), "Authorised officer"),
    (re.compile(r"leiter", re.I), "Head"),
    (re.compile(r"personal(?:referent|verantwortlich)", re.I), "HR"),
)


def title_hint(title: str | None) -> str | None:
    """A short English meaning of a German title, or None."""
    if not title:
        return None
    hints = []
    for pattern, hint in _TITLE_HINTS:
        if pattern.search(title) and hint not in hints:
            hints.append(hint)
    return " · ".join(hints) or None
