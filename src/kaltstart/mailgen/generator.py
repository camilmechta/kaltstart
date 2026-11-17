"""generate(): the subject and body of a spontaneous application.

A pure function: it reads its own templates and nothing else. Every
sentence is built here from finished phrases; the templates only arrange
them. Section numbers refer to
docs/superpowers/specs/2026-11-16-phase-3-mail-generator-design.md.
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from kaltstart.mailgen.choices import axes, subject, variant as choose_variant
from kaltstart.mailgen.models import (
    LANGUAGES, MAX_BODY_WORDS, MAX_EXAMPLE_CHARS, MAX_EXAMPLE_WORDS, MAX_NAME_CHARS,
    MAX_PROGRAMME_CHARS, MAX_TEXT_CHARS, MAX_TEXT_WORDS, REQUESTS,
    ROLES, STYLES, Company, Contact, Mail, MissingData, Round, Student, TooLong)
from kaltstart.mailgen.phrases import (
    amount, investor_phrase, request_phrase, role_name, role_paragraph, round_name,
    student_text)

_TITLES = frozenset(("dr", "prof", "mag", "ing", "dipl", "lic", "phd", "mba"))
# Stand-ins for the student's own texts when the generated parts are checked.
_STUDENT_TEXT = "Student text."
# The showcase sentence of the profile is the heart of every mail; its lead-in
# says why the reader is told it (decision D71).
# Three wordings each, so that mails to one company differ (wording 0 is the
# one of the reference mails).
_LEAD_INS = {
    ("en", "direct"): ("A bit about me:", "What I have done so far:", "One thing I am proud of:"),
    ("en", "round"): ("What I bring:", "What I have done so far:", "A recent example:"),
    ("en", "formal"): ("One example of my work:", "My most relevant experience:",
                       "A recent example of my work:"),
    ("de", "direct"): ("Kurz zu mir:", "Was ich bisher gemacht habe:", "Worauf ich stolz bin:"),
    ("de", "round"): ("Was ich mitbringe:", "Was ich bisher gemacht habe:",
                      "Ein aktuelles Beispiel:"),
    ("de", "formal"): ("Ein Beispiel aus meiner Arbeit:", "Meine wichtigste Erfahrung:",
                       "Ein aktuelles Beispiel meiner Arbeit:"),
}
_LINK = "https://example.com/link"

_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=False, trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=False,
    undefined=StrictUndefined)


# --- the deal: "your €8M Series A with X and others" --------------------------

def _deal(round: Round, language: str, article: str) -> str:
    """The round with its amount and first investor when known. `article` is
    the possessive the sentence needs ("your", "eurer", "Ihrer", ...)."""
    name, money, investor = round_name(round.stage, language), amount(round, language), \
        investor_phrase(round, language)
    if language == "en":
        text = f"{article} {money} {name}" if money else f"{article} {name}"
    else:
        text = f"{article} {name} über {money}" if money else f"{article} {name}"
    return f"{text} {investor}" if investor else text


def _role_words(role: str, language: str) -> str:
    """The role inside a sentence: "growth" in English; in German the name of
    the field, which the sentences introduce with "Bereich" ("im Bereich
    Produkt"), since "Produkt" or "Data" cannot stand alone."""
    name = role_name(role, language)
    return name.lower() if language == "en" else name


# --- openings, section 8.1: three wordings for Direct and Round, one for Formal

def _opening(style: str, language: str, round: Round, company: Company, role: str,
             number: int) -> str:
    role_text = _role_words(role, language)
    if language == "en":
        deal = _deal(round, "en", "your")
        if style == "direct":
            return (f"Congrats on {deal}!",
                    f"Congratulations on {deal}, great news!",
                    f"I just read about {deal}. Congrats!")[number]
        if style == "round":
            return (f"After {deal}, {company.name} is about to scale, and the {role_text} team "
                    f"will be central.",
                    f"{deal[0].upper()}{deal[1:]} is great news, and I would love to help with "
                    f"{role_text} as {company.name} scales.",
                    f"Congratulations on {deal}! A round like this usually means building out "
                    f"the {role_text} team, which is where I want to help.")[number]
        return (f"Congratulations on {deal}.",
                f"Congratulations on {deal}. The news caught my attention.",
                f"I read with interest about {deal}.")[number]
    if style == "direct":
        deal = _deal(round, "de", "eurer")
        return (f"Glückwunsch zu {deal}!",
                f"Herzlichen Glückwunsch zu {deal}, starke Neuigkeiten!",
                f"Ich habe gerade von {deal} gelesen. Glückwunsch!")[number]
    if style == "round":
        return (f"Nach {_deal(round, 'de', 'eurer')} wird {company.name} jetzt skalieren, und "
                f"der Bereich {role_text} wird dabei zentral sein.",
                f"{_deal(round, 'de', 'Eure')} ist eine tolle Nachricht, und im Bereich "
                f"{role_text} würde ich gerne mithelfen.",
                f"Glückwunsch zu {_deal(round, 'de', 'eurer')}! So eine Runde bedeutet meist, "
                f"den Bereich {role_text} auszubauen, und genau dort möchte ich helfen.")[number]
    deal = _deal(round, "de", "Ihrer")
    return (f"Herzlichen Glückwunsch zu {deal}.",
            f"Herzlichen Glückwunsch zu {deal}. Die Nachricht hat meine Aufmerksamkeit geweckt.",
            f"Mit Interesse habe ich von {deal} gelesen.")[number]


# --- the other blocks ----------------------------------------------------------

def _person(contact: Contact) -> str | None:
    name = " ".join((contact.person_name or "").split())
    return name or None


def _first_name(person: str) -> str:
    """The first word that is not a title ("Dr. Anna Muster" -> "Anna")."""
    words = person.split()
    names = [w for w in words if not (w.endswith(".") or w.lower() in _TITLES)]
    return names[0] if names else words[-1]


def _greeting(style: str, language: str, contact: Contact, company: Company) -> str:
    person = _person(contact)
    first = _first_name(person) if person else None
    if style == "formal":
        if language == "en":
            return f"Dear {person}," if person else f"Dear {company.name} team,"
        return f"Guten Tag {person}," if person else "Guten Tag,"
    end = "!" if style == "direct" else ","
    if language == "en":
        return f"Hi {first}{end}" if first else f"Hi {company.name} team{end}"
    return f"Hallo {first}{end}" if first else f"Hallo zusammen{end}"


def _intro(style: str, language: str, student: Student) -> str:
    request = request_phrase(student, language)
    if language == "en":
        if style == "formal":
            return (f"I study {student.programme} at the University of St. Gallen (HSG) "
                    f"and am applying for {request}.")
        return f"I study {student.programme} at HSG and am looking for {request}."
    if style == "formal":
        return (f"Ich studiere {student.programme} an der Universität St. Gallen (HSG) und "
                f"bewerbe mich um {request}.")
    return f"Ich studiere {student.programme} an der HSG und suche {request}."


def _close(style: str, language: str, role: str, team: bool, number: int = 0) -> str:
    role_text = _role_words(role, language)
    if language == "en":
        help_text = f"I'd love to help with {role_text}, or with whatever helps most."
        return {
            "direct": (f"{help_text} Would that work?", f"{help_text} Could that be useful to you?",
                       f"{help_text} Shall we talk?"),
            "round": ("Could we talk for 15 minutes?",
                      "Would you have 15 minutes this week or next?",
                      "Could we find 15 minutes for a short call?"),
            "formal": ("I would welcome a short call. Thank you for your time.",
                       "I would be glad to discuss this in a short call. Thank you for your time.",
                       "I look forward to hearing from you. Thank you for your consideration."),
        }[style][number]
    help_text = (f"Ich würde gerne im Bereich {role_text} mithelfen, oder dort, wo es am "
                 "meisten bringt.")
    you = "Habt ihr" if team else "Hast du"
    return {
        "direct": (f"{help_text} Würde das passen?",
                   f"{help_text} Wäre das für {'euch' if team else 'dich'} interessant?",
                   f"{help_text} Wollen wir kurz sprechen?"),
        "round": (f"{you} 15 Minuten für ein kurzes Gespräch?",
                  f"{you} nächste Woche 15 Minuten?",
                  "Können wir 15 Minuten telefonieren?"),
        "formal": ("Über ein kurzes Gespräch freue ich mich. Vielen Dank für Ihre Zeit.",
                   "Über die Gelegenheit zu einem kurzen Gespräch würde ich mich freuen. Vielen Dank.",
                   "Ich freue mich auf Ihre Rückmeldung. Vielen Dank für Ihre Zeit."),
    }[style][number]


_SIGN_OFF = {
    ("en", "direct"): "Best,", ("en", "round"): "Best regards,", ("en", "formal"): "Kind regards,",
    ("de", "direct"): "Viele Grüsse", ("de", "round"): "Beste Grüsse",
    ("de", "formal"): "Freundliche Grüsse",
}


def _programme_line(language: str, student: Student) -> str:
    return f"{student.programme}, HSG"


# --- checks --------------------------------------------------------------------

def _bounded(student: Student, texts: dict[str, str | None]) -> None:
    """Refuse what would not fit in the mail, naming the field."""
    if len(student.programme.strip()) > MAX_PROGRAMME_CHARS:
        raise TooLong("programme")
    for field in ("first_name", "last_name"):
        if len(getattr(student, field).strip()) > MAX_NAME_CHARS:
            raise TooLong(field)
    limits = {"example": (MAX_EXAMPLE_CHARS, MAX_EXAMPLE_WORDS),
              "company_line": (MAX_TEXT_CHARS, MAX_TEXT_WORDS)}
    for field, text in texts.items():
        chars, words = limits[field]
        if text and (len(text) > chars or len(text.split()) > words):
            raise TooLong(field)


def _missing(student: Student, contact: Contact, example: str | None) -> tuple[str, ...]:
    fields = []
    for name in ("first_name", "last_name", "programme"):
        if not (getattr(student, name) or "").strip():
            fields.append(name)
    if student.start_date is None:
        fields.append("start_date")
    if student.request == "internship" and not student.duration_months:
        fields.append("duration_months")
    if student.request == "part_time" and not student.workload_percent:
        fields.append("workload_percent")
    if not (contact.address or "").strip():
        fields.append("contact_address")
    if example is None:
        fields.append("example")
    return tuple(fields)


def _example_text(student: Student, language: str) -> str | None:
    if not student.examples:
        return None
    index = student.chosen_example if 0 <= student.chosen_example < len(student.examples) else 0
    example = student.examples[index]
    text = example.text_en if language == "en" else example.text_de
    return text if text and text.strip() else None


_GAPS = re.compile(r"[{}]|\bNone\b|  | [.,!?:]|\n\n\n")


def _check(generated: str, style: str, language: str) -> None:
    """A template bug, never a data problem: checked on the mail with the
    student's own texts replaced, since those are used as written."""
    if _GAPS.search(generated):
        raise AssertionError(f"{style}/{language}: a gap in the mail: {generated!r}")


# --- generate ------------------------------------------------------------------

def generate(student: Student, company: Company, round: Round, contact: Contact, *,
             style: str, language: str, company_line: str | None = None,
             variant: int | None = None) -> Mail:
    if style not in STYLES:
        raise ValueError(f"unknown style: {style}")
    if language not in LANGUAGES:
        raise ValueError(f"unknown language: {language}")
    if student.role not in ROLES:
        raise ValueError(f"unknown role: {student.role}")
    if student.request not in REQUESTS:
        raise ValueError(f"unknown request: {student.request}")
    if variant is not None and (not isinstance(variant, int) or variant < 0):
        raise ValueError(f"variant must be a count from 0: {variant}")
    line = company_line.strip() if company_line and company_line.strip() else None
    example = _example_text(student, language)
    _bounded(student, {"company_line": line, "example": example})
    missing = _missing(student, contact, example)
    if missing:
        raise MissingData(missing)

    # variant is how many mails were already kept for this company and round:
    # each axis takes its own wording from it (spec of 2026-11-16, section 4).
    k = choose_variant(student.id, company.id) if variant is None else variant
    subject_n, opening_n, lead_in_n, close_n, order = axes(k)
    team = _person(contact) is None
    link = (student.link or "").strip() or None
    # A name ending in a full stop ("Example Holdings Inc.") must not double it.
    opening = _opening(style, language, round, company, student.role, opening_n).replace("..", ".")
    parts = dict(
        greeting=_greeting(style, language, contact, company),
        opening=opening,
        intro=_intro(style, language, student),
        # The student's own sentence about the company, when given, replaces the
        # generic paragraph about the role (decision D71).
        role_paragraph=None if line else role_paragraph(student.role, language, style == "formal"),
        close=_close(style, language, student.role, team, close_n),
        intro_first=order == 0,
        sign_off=_SIGN_OFF[(language, style)],
        name=f"{student.first_name.strip()} {student.last_name.strip()}",
        programme_line=_programme_line(language, student),
    )
    template = _ENV.get_template(f"{style}_{language}.j2")
    lead_in = _LEAD_INS[(language, style)][lead_in_n]
    _check(template.render(showcase=f"{lead_in} {_STUDENT_TEXT}",
                           company_line=line and _STUDENT_TEXT, link=link and _LINK,
                           **parts).strip(), style, language)
    body = template.render(showcase=f"{lead_in} {student_text(example)}",
                           company_line=line and student_text(line), link=link,
                           **parts).strip()
    if len(body.split()) > MAX_BODY_WORDS:
        raise TooLong("body")
    return Mail(
        subject=subject(style, language, company.name, round_name(round.stage, language),
                        role_name(student.role, language), student.request, subject_n),
        body=body, language=language, style=style, used_company_line=line is not None)
