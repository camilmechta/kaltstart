from pathlib import Path

import pytest

from kaltstart.contacts.founders import ROLE_WORDS, extract_founders
from kaltstart.contacts.models import Page

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sites"


def names(body, kind="team"):
    page = Page("https://example.ch/team", kind, f"<html><body>{body}</body></html>")
    return [(f.name, f.role) for f in extract_founders(page)]


@pytest.mark.parametrize("body,expected", [
    ("<p>Geschäftsführer: Anna Muster</p>", [("Anna Muster", "Geschäftsführer")]),
    ("<p>Geschäftsführung / Geschäftsführer: Dr. Anna Muster, Jonas Beispiel</p>",
     [("Anna Muster", "Geschäftsführer"), ("Jonas Beispiel", "Geschäftsführer")]),
    ("<div><h3>Anna Muster</h3><p>Co-Founder &amp; CEO</p></div>", [("Anna Muster", "Co-Founder")]),
    ("<div><p>CEO</p><h3>Jonas von Beispiel</h3></div>", [("Jonas von Beispiel", "CEO")]),
    ("<p>Anna Muster, Founder</p>", [("Anna Muster", "Founder")]),
    ("<p>Gründerin Anna Maria Muster</p>", [("Anna Maria Muster", "Gründerin")]),
])
def test_names_next_to_a_role(body, expected):
    assert names(body) == expected


@pytest.mark.parametrize("body", [
    "<p>Founder of the Year Award</p>",
    "<p>Geschäftsführer: Example Ventures AG</p>",
    "<p>CEO Office 2nd Floor</p>",
    "<p>Our founders met in Zurich</p>",
    "<p>Backed by Founder Collective</p>",
])
def test_rejections(body):
    assert names(body) == []


def test_only_legal_and_team_pages_are_read():
    assert names("<p>Anna Muster, Founder</p>", kind="careers") == []
    assert names("<p>Anna Muster, Founder</p>", kind="legal") == [("Anna Muster", "Founder")]


def test_same_person_is_returned_once():
    assert names("<p>Anna Muster, Founder</p><p>CEO: Anna Muster</p>") == [("Anna Muster", "Founder")]


def test_source_url_is_the_page():
    page = Page("https://example.ch/impressum", "legal", "<p>Anna Muster, Founder</p>")
    assert extract_founders(page)[0].source_url == "https://example.ch/impressum"


def test_longer_role_words_come_first():
    assert ROLE_WORDS.index("Co-Founder") < ROLE_WORDS.index("Founder")
    assert ROLE_WORDS.index("Mitgründer") < ROLE_WORDS.index("Gründer")


def test_invented_german_legal_notice():
    html = (FIXTURES / "impressum_de.html").read_text(encoding="utf-8")
    page = Page("https://example.de/impressum", "legal", html)
    assert [(f.name, f.role) for f in extract_founders(page)] == [
        ("Anna Muster", "Geschäftsführer"), ("Jonas Beispiel", "Geschäftsführer")]


def test_invented_team_page_keeps_founders_only():
    html = (FIXTURES / "team_cards.html").read_text(encoding="utf-8")
    page = Page("https://example.ch/team", "team", html)
    assert [(f.name, f.role) for f in extract_founders(page)] == [
        ("Anna Muster", "Co-Founder"), ("Jonas Beispiel", "Co-Founder")]
