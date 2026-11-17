"""A name read on a site is shown and greeted only if it looks like a person's
(owner's review of the live site, 2026-11-17). Invented names only."""

import pytest

from kaltstart.contacts.names import clean_name, title_hint


@pytest.mark.parametrize("raw,expected", [
    ("Lina Beispiel", "Lina Beispiel"),
    ("MSc ETH Lina Beispiel", "Lina Beispiel"),
    ("MSc Eth Lina Beispiel", "Lina Beispiel"),
    ("BSc HSG Jonas Muster", "Jonas Muster"),
    ("Dr. med. Ana Probe", "Ana Probe"),
    ("Dipl.-Ing. Ana Probe", "Ana Probe"),
    ("Prof. Dr. Ana Probe", "Ana Probe"),
    ("Ana Probe, MBA", "Ana Probe"),
    ("Ana von der Probe", "Ana von der Probe"),
    ("Mateo de Ejemplo", "Mateo de Ejemplo"),
    ("  Lina   Beispiel ", "Lina Beispiel"),
])
def test_a_name_keeps_only_the_person(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize("raw", [
    "Was Einkauf",                 # a German question word
    "Unser Team",
    "Wie Wir Arbeiten",
    "What We Do",
    "Lina Beispiel.",              # a sentence
    "Lina Beispiel?",
    "lina beispiel",               # not capitalised
    "Lina",                        # one word
    "MSc ETH",                     # nothing left
    "Lina Beispiel Muster Probe Test Extra",   # too long for a name
    "Team 2026 Lina",
])
def test_what_is_not_a_person_is_dropped(raw):
    assert clean_name(raw) is None


@pytest.mark.parametrize("title,hint", [
    ("Geschäftsführer", "Managing director"),
    ("Geschäftsführerin", "Managing director"),
    ("Gründer & Lead Data Scientist", "Founder"),
    ("Mitgründerin und Geschäftsführerin", "Co-founder · Managing director"),
    ("Leiterin Marketing", "Head"),
    ("Vorstand", "Board member"),
    ("Head of Growth", None),
    ("CEO", None),
])
def test_common_german_titles_get_an_english_hint(title, hint):
    assert title_hint(title) == hint
