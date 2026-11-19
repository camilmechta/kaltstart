"""LinkedIn note and message (design 2026-11-19). The note never exceeds 200
characters: counted by code on every combination, never estimated."""

import itertools

import pytest

from kaltstart.mailgen.linkedin import (
    MAX_MESSAGE_WORDS, MAX_NOTE_CHARS, linkedin_message, linkedin_note)
from kaltstart.mailgen.models import LANGUAGES, REQUESTS, ROLES, STYLES, Example
from tests.mailgen.helpers import company, round_, student
from tests.mailgen.test_matrix import (
    LONG_COMPANY, LONG_LINE, LONG_PROGRAMME, LONG_TEXT, STAGES)

LONG_PERSON = "Prof. Dr. Anna-Maria Muster-Beispielfrau"          # 40 characters
LONG_UNIVERSITY = "University of Applied Sciences"                  # 30 characters


def long_student(role, request):
    return student(role=role, request=request, programme=LONG_PROGRAMME,
                   first_name="Maria Luisa Annabelle", last_name="van der Berg-Muster",
                   level="master", university=LONG_UNIVERSITY,
                   duration_months=6 if request == "internship" else None,
                   workload_percent=40 if request == "part_time" else None,
                   examples=(Example(LONG_TEXT, LONG_TEXT),))


def test_the_limits():
    assert (MAX_NOTE_CHARS, MAX_MESSAGE_WORDS) == (200, 190)


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_no_note_ever_exceeds_200_characters(style, language):
    count = 0
    for role, request, stage, name, person in itertools.product(
            ROLES, REQUESTS, STAGES + (None,), (LONG_COMPANY, "Ab"), (LONG_PERSON, "Al")):
        note = linkedin_note(long_student(role, request), company(name=name),
                             round_(stage=stage), person, style=style, language=language)
        assert 0 < len(note) <= MAX_NOTE_CHARS, (style, language, role, request, stage, len(note), note)
        assert "None" not in note and "  " not in note and "{" not in note, note
        count += 1
    assert count == len(ROLES) * len(REQUESTS) * 5 * 2 * 2


def test_the_richest_note_is_used_when_it_fits():
    note = linkedin_note(student(level="master", university="HSG"), company(), round_(),
                         "Anna Muster", style="direct", language="en")
    assert note == ("Hi Anna, congrats on Example Robotics's Series A! I'm a Master's student "
                    "at HSG looking for an internship in growth and would love to connect. Lea")


def test_the_formal_and_german_notes():
    formal = linkedin_note(student(level="master", university="HSG"), company(), round_(),
                           "Anna Muster", style="formal", language="en")
    assert formal.startswith("Dear Anna Muster, congratulations on") and formal.endswith("Lea Beispiel")
    german = linkedin_note(student(level="bachelor", university="HSG"), company(), round_(),
                           "Anna Muster", style="direct", language="de")
    assert german.startswith("Hallo Anna, ") and "Praktikum" in german and german.endswith("Lea")
    assert len(formal) <= 200 and len(german) <= 200


def test_a_name_too_long_for_every_ladder_step_still_gives_a_note():
    name = "Anna " + "Muster" * 40
    note = linkedin_note(student(), company(), round_(), name, style="formal", language="en")
    assert len(note) <= MAX_NOTE_CHARS


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_message_stays_short(style, language):
    for role, request, line, variant in itertools.product(
            ROLES, REQUESTS, (LONG_LINE, None), range(6)):
        text = linkedin_message(long_student(role, request), company(name=LONG_COMPANY),
                                round_(investors=("Example Ventures Growth Opportunities",
                                                  "Other Capital")),
                                LONG_PERSON, style=style, language=language,
                                company_line=line, variant=variant)
        assert len(text.split()) <= MAX_MESSAGE_WORDS, (style, language, len(text.split()))
        assert "CV" not in text and "Lebenslauf" not in text and "PS:" not in text


def test_the_message_reads_like_a_chat():
    text = linkedin_message(student(), company(), round_(), "Anna Muster", style="direct",
                            language="en", company_line=None, variant=0)
    paragraphs = text.split("\n\n")
    assert paragraphs[0] == "Hi Anna!" and paragraphs[1] == "Thanks for connecting!"
    assert "I grew a student newsletter from 0 to 4000 readers in one year." in text
    assert paragraphs[-1] == "Lea"
