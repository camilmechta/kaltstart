from datetime import date

import pytest

from kaltstart.mailgen.models import ROLES
from kaltstart.mailgen.phrases import (
    amount, investor_phrase, long_date, request_phrase, role_name, role_paragraph,
    role_words, round_name, student_text)
from tests.mailgen.helpers import round_, student


@pytest.mark.parametrize("changes,en,de", [
    (dict(amount_eur=8_000_000), "€8M", "8 Mio. €"),
    (dict(amount_native=2_500_000, currency="CHF"), "CHF 2.5M", "2,5 Mio. CHF"),
    (dict(amount_native=40_000_000, currency="USD"), "$40M", "40 Mio. $"),
    (dict(amount_native=3_000_000, currency="GBP"), "£3M", "3 Mio. £"),
    (dict(amount_native=30_000_000, currency="SEK"), "SEK 30M", "30 Mio. SEK"),
    (dict(amount_eur=9_960_000), "€10M", "10 Mio. €"),
    (dict(amount_eur=1_250_000), "€1.2M", "1,2 Mio. €"),
    (dict(amount_eur=4_000_000, amount_native=4_400_000, currency=""), "€4M", "4 Mio. €"),
])
def test_amount(changes, en, de):
    values = dict(amount_eur=None, amount_native=None, currency=None)
    values.update(changes)
    assert amount(round_(**values), "en") == en
    assert amount(round_(**values), "de") == de


@pytest.mark.parametrize("value", [0, None])
def test_no_amount(value):
    assert amount(round_(amount_eur=value, amount_native=None), "en") is None


def test_one_investor():
    r = round_(investors=("Example Ventures",))
    assert investor_phrase(r, "en") == "backed by Example Ventures"
    assert investor_phrase(r, "de") == "mit Example Ventures"


def test_several_investors():
    r = round_(investors=("Example Ventures", "Other Capital", "Third Fund"))
    assert investor_phrase(r, "en") == "with Example Ventures and others"
    assert investor_phrase(r, "de") == "mit Example Ventures und weiteren"


@pytest.mark.parametrize("investors", [(), ("X" * 41,)])
def test_no_usable_investor(investors):
    assert investor_phrase(round_(investors=investors), "en") is None


def test_never_claims_a_lead():
    for investors in (("A Ventures",), ("A Ventures", "B")):
        for language in ("en", "de"):
            text = investor_phrase(round_(investors=investors), language)
            assert "led" not in text and "angef" not in text


@pytest.mark.parametrize("stage,en,de", [
    ("Seed", "seed round", "Seed-Runde"), ("Series A", "Series A", "Series A"),
    ("Pre-Seed", "pre-seed round", "Pre-Seed-Runde"), ("Growth/Late", "growth round", "Wachstumsrunde"),
    ("Other", "funding round", "Finanzierungsrunde"),
    ("Crowdfunding", "funding round", "Finanzierungsrunde"),
    (None, "funding round", "Finanzierungsrunde"),
    ("Debt", "financing", "Finanzierung"), ("Grant", "grant", "Förderung"),
])
def test_round_name(stage, en, de):
    assert round_name(stage, "en") == en
    assert round_name(stage, "de") == de


def test_long_date():
    assert long_date(date(2027, 4, 1), "en") == "1 April 2027"
    assert long_date(date(2027, 4, 1), "de") == "1. April 2027"
    assert long_date(date(2027, 3, 15), "de") == "15. März 2027"


def test_request_phrase():
    assert request_phrase(student(), "en") == "an internship from 1 April 2027 for 3 months"
    assert request_phrase(student(), "de") == "ein Praktikum ab 1. April 2027 für 3 Monate"
    part = student(request="part_time", duration_months=None, workload_percent=40)
    assert request_phrase(part, "en") == "part-time work (40 %) from 1 April 2027"
    assert request_phrase(part, "de") == "eine Teilzeitstelle (40 %) ab 1. April 2027"


@pytest.mark.parametrize("text,expected", [
    ("  I tried your app ", "I tried your app."),
    ("Would love that!", "Would love that!"),
    ("Why not?", "Why not?"),
    ("Done.", "Done."),
])
def test_student_text(text, expected):
    assert student_text(text) == expected


def test_role_names():
    assert [role_name(r, "en") for r in ROLES] == [
        "Product", "Growth", "Data", "Operations", "Business development",
        "Software & AI", "R&D & Hardware"]
    assert role_name("product", "de") == "Produkt"
    assert role_name("software_ai", "de") == "Software & KI"
    assert role_name("rd_hardware", "de") == "Forschung & Entwicklung"


@pytest.mark.parametrize("role,language,expected", [
    ("growth", "en", "growth"), ("product", "de", "Produkt"),
    ("software_ai", "en", "software and AI"), ("rd_hardware", "en", "R&D and hardware"),
    ("software_ai", "de", "Software & KI"), ("rd_hardware", "de", "Forschung & Entwicklung")])
def test_role_words(role, language, expected):
    assert role_words(role, language) == expected


def test_technical_paragraphs():
    assert role_paragraph("software_ai", "en", False) == (
        "After a round, the team must ship faster. I would like to help build "
        "and ship the next features.")
    assert role_paragraph("rd_hardware", "en", False) == (
        "New funding turns prototypes into products. I would like to help design, "
        "build and test the next iterations.")
    assert role_paragraph("software_ai", "de", False) == (
        "Nach einer Runde muss das Team schneller liefern. Ich würde gerne helfen, "
        "die nächsten Features zu bauen und auszuliefern.")
    assert role_paragraph("rd_hardware", "de", False) == (
        "Neues Kapital macht aus Prototypen Produkte. Ich würde gerne helfen, "
        "die nächsten Iterationen zu entwerfen, zu bauen und zu testen.")


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize("formal", [False, True])
def test_role_paragraph(role, language, formal):
    text = role_paragraph(role, language, formal)
    assert 8 <= len(text.split()) <= 35
    assert "ß" not in text
    if language == "de":
        words = text.replace(",", " ").replace(".", " ").split()
        informal = {"du", "dich", "dir", "dein", "deine", "deinem", "deinen", "deiner", "euch", "euer", "eure", "eurem", "euren"}
        if formal:
            assert not informal & set(words)
        else:
            assert "Sie" not in words and "Ihnen" not in words and "Ihr" not in words
