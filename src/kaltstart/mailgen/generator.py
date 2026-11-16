"""generate(): the subject and body of a spontaneous application.

A pure function: it reads its own templates and nothing else. Every
sentence is built here from finished phrases; the templates only arrange
them. Section numbers refer to
docs/superpowers/specs/2026-11-16-phase-3-mail-generator-design.md.
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from kaltstart.mailgen.choices import subject, variant as choose_variant
from kaltstart.mailgen.models import (
    LANGUAGES, STYLES, Company, Contact, Mail, MissingData, Round, Student)
from kaltstart.mailgen.phrases import (
    amount, investor_phrase, request_phrase, role_name, role_paragraph, round_name,
    student_text)

MAX_BODY_WORDS = 150
MAX_TEXT_CHARS = 200

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
    """The role inside a sentence: lower case in English, a noun in German."""
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
            return (f"With {deal}, {company.name} is about to scale, and {role_text} will be central.",
                    f"{deal[0].upper()}{deal[1:]} is great news, and I would love to help with "
                    f"{role_text} as {company.name} scales.",
                    f"Congratulations on {deal}! A round like this usually means building out "
                    f"{role_text}, which is where I want to help.")[number]
        return f"Congratulations on {deal}."
    if style == "direct":
        deal = _deal(round, "de", "eurer")
        return (f"Glückwunsch zu {deal}!",
                f"Herzlichen Glückwunsch zu {deal}, starke Neuigkeiten!",
                f"Ich habe gerade von {deal} gelesen. Glückwunsch!")[number]
    if style == "round":
        return (f"Mit {_deal(round, 'de', 'eurer')} wird {company.name} jetzt skalieren, und "
                f"{role_text} wird dabei zentral sein.",
                f"{_deal(round, 'de', 'Eure')} ist eine tolle Nachricht, und bei {role_text} "
                f"würde ich gerne mithelfen.",
                f"Glückwunsch zu {_deal(round, 'de', 'eurer')}! So eine Runde bedeutet meist, "
                f"{role_text} auszubauen, und genau dort möchte ich helfen.")[number]
    return f"Herzlichen Glückwunsch zu {_deal(round, 'de', 'Ihrer')}."


# --- the other blocks ----------------------------------------------------------

def _greeting(style: str, language: str, contact: Contact, company: Company) -> str:
    person = contact.person_name
    first = person.split()[0] if person else None
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
        return f"I'm a {student.programme} student at HSG, looking for {request}."
    if style == "formal":
        return (f"Ich studiere {student.programme} an der Universität St. Gallen (HSG) und "
                f"bewerbe mich um {request}.")
    return f"Ich studiere {student.programme} an der HSG und suche {request}."


def _close(style: str, language: str, role: str, team: bool) -> str:
    role_text = _role_words(role, language)
    if language == "en":
        return {
            "direct": f"I'd love to help with {role_text}, or with whatever helps most. Would that work?",
            "round": "Could we talk for 15 minutes?",
            "formal": "I would welcome a short call. Thank you for your time.",
        }[style]
    return {
        "direct": f"Ich würde gerne bei {role_text} mithelfen, oder dort, wo es am meisten bringt. "
                  "Würde das passen?",
        "round": ("Habt ihr 15 Minuten für ein kurzes Gespräch?" if team
                  else "Hast du 15 Minuten für ein kurzes Gespräch?"),
        "formal": "Über ein kurzes Gespräch freue ich mich. Vielen Dank für Ihre Zeit.",
    }[style]


_SIGN_OFF = {
    ("en", "direct"): "Best,", ("en", "round"): "Best regards,", ("en", "formal"): "Kind regards,",
    ("de", "direct"): "Viele Grüsse", ("de", "round"): "Beste Grüsse",
    ("de", "formal"): "Freundliche Grüsse",
}


def _programme_line(language: str, student: Student) -> str:
    return f"{student.programme}, HSG"


# --- checks --------------------------------------------------------------------

def _missing(student: Student, contact: Contact, core: str | None) -> tuple[str, ...]:
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
    if core is None:
        fields.append("company_line_or_example")
    return tuple(fields)


def _example_text(student: Student, language: str) -> str | None:
    if not student.examples:
        return None
    index = student.chosen_example if 0 <= student.chosen_example < len(student.examples) else 0
    example = student.examples[index]
    text = example.text_en if language == "en" else example.text_de
    return text if text and text.strip() else None


_GAPS = re.compile(r"[{}]|\bNone\b|  | [.,!?:]|\n\n\n")


def _check(body: str, style: str, language: str) -> None:
    """A template bug, never a data problem: the tests run every combination."""
    if _GAPS.search(body):
        raise AssertionError(f"{style}/{language}: a gap in the mail: {body!r}")
    if len(body.split()) > MAX_BODY_WORDS:
        raise AssertionError(f"{style}/{language}: {len(body.split())} words")


# --- generate ------------------------------------------------------------------

def generate(student: Student, company: Company, round: Round, contact: Contact, *,
             style: str, language: str, company_line: str | None = None,
             variant: int | None = None) -> Mail:
    if style not in STYLES:
        raise ValueError(f"unknown style: {style}")
    if language not in LANGUAGES:
        raise ValueError(f"unknown language: {language}")
    line = company_line.strip() if company_line and company_line.strip() else None
    example = _example_text(student, language)
    for text in (line, example):
        if text and len(text) > MAX_TEXT_CHARS:
            raise ValueError(f"a text of the student is longer than {MAX_TEXT_CHARS} characters")
    core = line or example
    missing = _missing(student, contact, core)
    if missing:
        raise MissingData(missing)

    number = choose_variant(student.id, company.id) if variant is None else variant
    if style == "formal":
        number = 0
    team = contact.person_name is None
    body = _ENV.get_template(f"{style}_{language}.j2").render(
        greeting=_greeting(style, language, contact, company),
        opening=_opening(style, language, round, company, student.role, number),
        intro=_intro(style, language, student),
        core=student_text(core),
        role_paragraph=role_paragraph(student.role, language, style == "formal"),
        close=_close(style, language, student.role, team),
        link=(student.link or "").strip() or None,
        sign_off=_SIGN_OFF[(language, style)],
        name=f"{student.first_name.strip()} {student.last_name.strip()}",
        programme_line=_programme_line(language, student),
    ).strip()
    _check(body, style, language)
    return Mail(
        subject=subject(style, language, company.name, round_name(round.stage, language),
                        role_name(student.role, language), student.request),
        body=body, language=language, style=style, used_company_line=line is not None)
