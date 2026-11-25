"""How a university reads in a mail (D113, review 2026-11-25): "at the
University of Zurich" in English, the German name and article in German."""

import pytest

from kaltstart.mailgen.generator import generate
from kaltstart.mailgen.linkedin import linkedin_note
from tests.mailgen.helpers import company, contact, round_, student


def body(university, language, style="direct"):
    return generate(student(level="master", university=university), company(), round_(),
                    contact(person_name=None if style == "formal" else "Anna Muster"),
                    style=style, language=language, variant=0).body


@pytest.mark.parametrize("style,expected", [
    ("direct", "I'm doing a Master in Business Innovation at the University of Zurich and"),
    ("formal", "I am completing a Master in Business Innovation at the University of Zurich and"),
])
def test_english_says_the_university_of(style, expected):
    text = body("University of Zurich", "en", style)
    assert expected in text
    assert "Master in Business Innovation, University of Zurich" in text      # signature


def test_english_keeps_a_name_without_article():
    assert "at TUM and" in body("TUM", "en") and "at the TUM" not in body("TUM", "en")


@pytest.mark.parametrize("university,phrase,signature", [
    ("University of Vienna", "an der Universität Wien und", "Master in Business Innovation, Universität Wien"),
    ("University of Zurich", "an der Universität Zürich und", "Master in Business Innovation, Universität Zürich"),
    ("KIT", "am KIT und", "Master in Business Innovation, KIT"),
    ("ETH Zurich", "an der ETH Zürich und", "Master in Business Innovation, ETH Zürich"),
    ("Universität Bern", "an der Universität Bern und", "Master in Business Innovation, Universität Bern"),
])
def test_german_uses_the_german_name_and_article(university, phrase, signature):
    text = body(university, "de")
    assert phrase in text and signature in text


def test_the_linkedin_note_reads_the_same_way():
    en = linkedin_note(student(level="master", university="University of Basel"), company(), round_(),
                       "Anna Muster", style="direct", language="en")
    de = linkedin_note(student(level="master", university="KIT"), company(), round_(),
                       "Anna Muster", style="direct", language="de")
    assert "at the University of Basel" in en and "am KIT" in de and "an der KIT" not in de
