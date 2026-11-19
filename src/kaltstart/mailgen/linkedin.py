"""LinkedIn texts (design 2026-11-19): a connection note and a message for
after the connection is accepted. Pure functions, no AI, no network.

The note never exceeds MAX_NOTE_CHARS: candidates go from the richest to the
shortest, and the first one whose real length (Python `len`) fits is used.
The last candidate holds no name at all, so a note always exists.
"""

from kaltstart.mailgen import generator as g
from kaltstart.mailgen.choices import axes
from kaltstart.mailgen.models import Company, Round, Student
from kaltstart.mailgen.phrases import role_paragraph, role_words, round_name, student_text

MAX_NOTE_CHARS = 200             # a free LinkedIn account's limit (300 before 2025)
MAX_MESSAGE_WORDS = 190          # the longest case measured: 187, every student text at its longest


def note_length(text: str) -> int:
    """The length LinkedIn counts: UTF-16 units, so an emoji counts 2."""
    return len(text.encode("utf-16-le")) // 2


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _first(name: str) -> str:
    return g.first_name(" ".join(name.split()))


def _level(student: Student, language: str) -> str | None:
    if student.level not in ("bachelor", "master"):
        return None
    if language == "en":
        return "Master's" if student.level == "master" else "Bachelor's"
    return "im Master" if student.level == "master" else "im Bachelor"


def _note_candidates(student: Student, company: Company, round: Round, person: str,
                     style: str, language: str) -> list[str]:
    person = " ".join(person.split())
    first = _first(person)
    me = (f"{_clean(student.first_name)} {_clean(student.last_name)}" if style == "formal"
          else _clean(student.first_name))
    uni = " ".join((student.university or "HSG").split())
    stage = round_name(round.stage, language)
    role = role_words(student.role, language)
    level = _level(student, language)
    name = _clean(company.name)
    part_time = student.request == "part_time"
    if language == "en":
        req = f"a part-time role in {role}" if part_time else f"an internship in {role}"
        short = "a part-time role" if part_time else "an internship"
        who = f"a {level} student at {uni}" if level else f"a student at {uni}"
        if style == "formal":
            return [
                f"Dear {person}, congratulations on the {stage} at {name}. I am {who} seeking {req} "
                f"and would be glad to connect. {me}",
                f"Dear {person}, congratulations on the funding round at {name}. I am {who} "
                f"seeking {req} and would be glad to connect. {me}",
                f"Dear {person}, congratulations on the round at {name}. I am a student seeking {req} "
                f"and would be glad to connect. {me}",
                f"Dear {person}, congratulations on your round. I would be glad to connect about "
                f"{short}. {me}",
                f"Congratulations on your round. I would be glad to connect about {short}.",
            ]
        return [
            f"Hi {first}, congrats on the {stage} at {name}! I'm {who} looking for {req} and would "
            f"love to connect. {me}",
            f"Hi {first}, congrats on the funding round at {name}! I'm {who} looking for {req} "
            f"and would love to connect. {me}",
            f"Hi {first}, congrats on the round at {name}! I'm a student looking for {req} and would "
            f"love to connect. {me}",
            f"Hi {first}, congrats on the round at {name}! I'd love to connect about {short}. {me}",
            f"Hi {first}, congrats on your round! I'd love to connect about {short}. {me}",
            f"Congrats on your round! I'd love to connect about {short}.",
        ]
    req = (f"eine Teilzeitstelle im Bereich {role}" if part_time
           else f"ein Praktikum im Bereich {role}")
    short = "eine Teilzeitstelle" if part_time else "ein Praktikum"
    studies = f"Ich studiere {level} an der {uni}" if level else f"Ich studiere an der {uni}"
    if style == "formal":
        return [
            f"Guten Tag {person}, herzlichen Glückwunsch zur {stage} von {name}. {studies} und "
            f"suche {req}. Ich würde mich freuen, mich mit Ihnen zu vernetzen. {me}",
            f"Guten Tag {person}, herzlichen Glückwunsch zur Finanzierungsrunde. {studies} und "
            f"suche {req}. Gerne würde ich mich mit Ihnen vernetzen. {me}",
            f"Guten Tag {person}, herzlichen Glückwunsch zur Finanzierungsrunde. Ich suche {req} "
            f"und würde mich gerne vernetzen. {me}",
            f"Guten Tag {person}, herzlichen Glückwunsch zur Finanzierungsrunde. Gerne würde ich "
            f"mich wegen {'einer Teilzeitstelle' if part_time else 'eines Praktikums'} "
            f"vernetzen. {me}",
            f"Guten Tag, herzlichen Glückwunsch zur Finanzierungsrunde. Gerne würde ich mich "
            f"wegen {'einer Teilzeitstelle' if part_time else 'eines Praktikums'} vernetzen.",
            "Herzlichen Glückwunsch zur Finanzierungsrunde. Gerne würde ich mich vernetzen.",
        ]
    return [
        f"Hallo {first}, Glückwunsch zur {stage} von {name}! {studies} und suche {req}. "
        f"Ich würde mich freuen, mich mit dir zu vernetzen. {me}",
        f"Hallo {first}, Glückwunsch zur Finanzierungsrunde! {studies} und suche {req}. "
        f"Ich würde mich freuen, mich mit dir zu vernetzen. {me}",
        f"Hallo {first}, Glückwunsch zur Finanzierungsrunde! Ich suche {req} und würde mich "
        f"gerne mit dir vernetzen. {me}",
        f"Hallo {first}, Glückwunsch zur Finanzierungsrunde! Ich suche {short} und würde "
        f"mich gerne mit dir vernetzen. {me}",
        f"Hallo {first}, Glückwunsch zur Finanzierungsrunde! Gerne würde ich mich mit dir "
        f"vernetzen.",
        "Glückwunsch zur Finanzierungsrunde! Ich würde mich freuen, uns zu vernetzen.",
    ]


def linkedin_note(student: Student, company: Company, round: Round, person_name: str, *,
                  style: str, language: str) -> str:
    """The richest connection note that fits in MAX_NOTE_CHARS characters."""
    candidates = _note_candidates(student, company, round, person_name, style, language)
    return next(text for text in candidates if note_length(text) <= MAX_NOTE_CHARS)


_THANKS = {("en", False): "Thanks for connecting!",
           ("en", True): "Thank you for accepting my request.",
           ("de", False): "Danke fürs Vernetzen!",
           ("de", True): "Vielen Dank, dass Sie meine Anfrage angenommen haben."}


def linkedin_message(student: Student, company: Company, round: Round, person_name: str, *,
                     style: str, language: str, company_line: str | None,
                     variant: int) -> str:
    """The message once the connection is accepted: the mail's core, without
    subject, programme line, CV sentence or PS."""
    formal = style == "formal"
    person = " ".join(person_name.split())
    first = _first(person)
    if language == "en":
        greeting = f"Dear {person}," if formal else (f"Hi {first}!" if style == "direct"
                                                     else f"Hi {first},")
    else:
        greeting = f"Guten Tag {person}," if formal else (f"Hallo {first}!" if style == "direct"
                                                          else f"Hallo {first},")
    _subject_n, opening_n, lead_in_n, close_n, _order = axes(variant)
    opening = g._opening(style, language, round, company, student.role, opening_n).replace("..", ".")
    example = g._example_text(student, language)
    lead_in = g._LEAD_INS[(language, style)][lead_in_n]
    line = company_line.strip() if company_line and company_line.strip() else None
    parts = [greeting, _THANKS[(language, formal)], f"{opening} {g._intro(style, language, student)}"]
    if example:
        parts.append(f"{lead_in} {student_text(example)}")
    parts.append(student_text(line) if line else role_paragraph(student.role, language, formal))
    parts.append(g._close(style, language, student.role, False, close_n))
    parts.append(f"{student.first_name.strip()} {student.last_name.strip()}" if formal
                 else student.first_name.strip())
    return "\n\n".join(parts)
