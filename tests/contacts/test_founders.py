from pathlib import Path

import pytest

from kaltstart.contacts.founders import ROLE_WORDS, extract_founders
from kaltstart.contacts.models import Page

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sites"


COMPANY = "Example Robotics"


def names(body, kind="team", company=COMPANY):
    page = Page("https://example.ch/team", kind, f"<html><body>{body}</body></html>")
    return [(f.name, f.role) for f in extract_founders(page, company)]


def card(name, role, name_tag="div", role_tag="div"):
    return f"<div><{name_tag}>{name}</{name_tag}><{role_tag}>{role}</{role_tag}></div>"


@pytest.mark.parametrize("body,expected", [
    ("<p>Geschäftsführer: Anna Muster</p>", [("Anna Muster", "Geschäftsführer")]),
    ("<p>Geschäftsführung / Geschäftsführer: Dr. Anna Muster, Jonas Beispiel</p>",
     [("Anna Muster", "Geschäftsführer"), ("Jonas Beispiel", "Geschäftsführer")]),
    ("<div><h3>Anna Muster</h3><p>Co-Founder &amp; CEO</p></div>", [("Anna Muster", "Co-Founder")]),
    ("<div><p>CEO</p><h3>Jonas von Beispiel</h3></div>", [("Jonas von Beispiel", "CEO")]),
    ("<p>Anna Muster, Founder</p>", [("Anna Muster", "Founder")]),
    ("<p>Gründerin Anna Maria Muster</p>", [("Anna Maria Muster", "Gründerin")]),
    # The label before a colon is never the name.
    ("<p>Vertretungsberechtigte Person: Dr. Anna Muster, Geschäftsführerin</p>",
     [("Anna Muster", "Geschäftsführerin")]),
    # Each role binds to its own name: only founder roles are returned.
    ("<p>CEO: Anna Muster, CTO: Peter Beispiel, CFO: Clara Vorlage</p>", [("Anna Muster", "CEO")]),
    ("<p>Anna Muster (CEO) and Peter Beispiel (CTO)</p>", [("Anna Muster", "CEO")]),
    ("<p>ANNA MUSTER, Founder</p>", [("Anna Muster", "Founder")]),
])
def test_names_next_to_a_role(body, expected):
    assert names(body) == expected


@pytest.mark.parametrize("body", [
    "<p>Founder of the Year Award</p>",
    "<p>Geschäftsführer: Example Ventures AG</p>",
    "<p>CEO Office 2nd Floor</p>",
    "<p>Our founders met in Zurich</p>",
    "<p>Backed by Founder Collective</p>",
    "<p>Verantwortliche Stelle: Beispiel Robotics GmbH, Geschäftsleitung</p>",
    "<p>About Us</p><p>Founder Story</p>",
    "<p>Message From Our CEO</p>",
    "<p>Dear Friends</p><p>CEO</p>",
    "<p>Investor, Founder of Example Ventures</p>",
    "<p>Advisor, former CEO at Example Corp</p>",
    "<p>Founder Associate: Mia Probe</p>",
    "<p>Head of CEO Office: Mia Probe</p>",
    "<p>Former CEO: Mia Probe</p>",
    "<blockquote><p>A great product, says Hans Probe, CEO of Example Bank</p></blockquote>",
    "<nav><span>Founder</span><span>Anna Muster</span></nav>",
    # Running prose is never read: it is where job titles and organisations
    # were mistaken for people on real sites.
    "<p>Our CEO Anna Muster previously worked at Other Labs</p>",
    "<p>The core mechanism emerged from doctoral research at a university (Dr. Anna Muster, CEO).</p>",
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


# Layouts seen on real team pages (first measurement), rebuilt with invented people.
@pytest.mark.parametrize("body,expected", [
    (card("Anna Muster", "Chief Executive Officer"), [("Anna Muster", "Chief Executive Officer")]),
    (card("Dr Jonas Beispiel", "Chief Technology Officer &amp; Co-Founder"),
     [("Jonas Beispiel", "Co-Founder")]),
    (card("Nico Vorlage, MRICS", "Co-Founder &amp; CCO", "h3", "p"), [("Nico Vorlage", "Co-Founder")]),
    (card("Prof Clara Stark", "Co-Founder, Advisor &amp; ETH Professor"), [("Clara Stark", "Co-Founder")]),
    (card("Nikita Probe", "Product Owner und Co-Founder"), [("Nikita Probe", "Co-Founder")]),
    (card("Gregor Entwurf", "Founder - CEO/CTO", "h3", "p"), [("Gregor Entwurf", "Founder")]),
    # The role names this very company.
    (card("Mia Vorlage", "Co-Founder Example Robotics, Sr. Investment Manager, Other Ventures"),
     [("Mia Vorlage", "Co-Founder")]),
    (card("Jean Probe", "CEO @Example Robotics", "div", "p"), [("Jean Probe", "CEO")]),
    (card("Lukas Muster und Daniel Beispiel", "Gründer der Example Robotics AG", "b", "div"),
     [("Lukas Muster", "Gründer"), ("Daniel Beispiel", "Gründer")]),
    # Name and role on one line.
    ("<h2>Esmeralda Muster, MBA - CEO &amp; Co-Founder</h2>", [("Esmeralda Muster", "Co-Founder")]),
    ("<h2>ESMERALDA MUSTER, MBA CEO and Co-Founder</h2>", [("Esmeralda Muster", "Co-Founder")]),
])
def test_real_layouts(body, expected):
    assert names(body) == expected


@pytest.mark.parametrize("body", [
    # The role is held at another organisation.
    card("Petra Probe", "CEO at Other Works"),
    card("Petra Probe", "Board Member at Example Robotics, founder and former CEO of Other Fiber Company"),
    card("Petra Probe", "Board Member at Example Robotics, CEO at Other One, Ex-CEO at Third Co"),
    card("Nina Entwurf", "Textile Advisor &amp; Founder Other Fabrics Expo"),
    card("Hans Probe", "CEO Other Group (Family Office), Business Angel"),
    # The neighbouring block is not a person's name.
    card("Chief Technology Officer", "Co-Founder"),
    card("Example Robotics", "CEO", "h2", "p"),
    card("Other Capital Partners", "Founder"),
    "<ul><li>25+ years in micro-optics and photonics</li><li>Co-founder &amp; CTO, Other Optics (acquired)</li></ul>",
    "<ul><li>Technical Project Lead &amp; Co-founder, Other Light Labs (acquired by a group)</li></ul>",
])
def test_real_false_positives_are_rejected(body):
    assert names(body) == []


def test_home_page_team_section_is_read():
    body = card("Gregor Entwurf", "Founder - CEO/CTO", "h3", "p")
    assert names(body, kind="home") == [("Gregor Entwurf", "Founder")]
    assert names(body, kind="contact") == []


def test_without_a_company_name_any_organisation_after_the_role_rejects():
    body = card("Jean Probe", "CEO @Example Robotics")
    assert names(body, company=None) == []
    assert names(card("Anna Muster", "Co-Founder &amp; CEO"), company=None) == [
        ("Anna Muster", "Co-Founder")]


# Second measurement: names one level up from the role, and customer testimonials.
@pytest.mark.parametrize("body,expected", [
    # The name is the neighbour of the role's parent, not of the role itself.
    ('<div class="member"><div>Leo Muster</div><div><p>Founder &amp; CEO​</p></div></div>',
     [("Leo Muster", "Founder")]),
    ("<div><h3>Dr. Donato Probe</h3><div><span>CEO &amp; Co-founder</span></div></div>",
     [("Donato Probe", "Co-Founder")]),
    # An empty neighbour (a picture) is skipped.
    ("<div><div>Anna Muster</div><div><div></div><p>Co-founder</p></div></div>",
     [("Anna Muster", "Co-Founder")]),
    (card("Anna Muster", "CEO, Example Robotics"), [("Anna Muster", "CEO")]),
])
def test_names_one_level_up(body, expected):
    assert names(body) == expected


QUOTE = "“They cut our planning time in half and we would not go back to the old way.”"


@pytest.mark.parametrize("body", [
    # Four testimonial layouts seen on real home pages.
    f'<figure class="slide"><p>{QUOTE}</p><div><p><span>Marc Probe</span><span>, CEO, Other Fuels</span></p></div></figure>',
    f"<div><div>{QUOTE}</div><div><div>Dr. Toby Probe , Otherix CEO</div></div></div>",
    f"<div><div>{QUOTE}</div><div><div><div>Raphael Probe</div><div>CEO, Othergem</div></div></div></div>",
    "<figure><blockquote>A quote without marks about the savings they made last year.</blockquote>"
    "<figcaption><div><span>Phil Probe</span><span>Founder</span></div></figcaption></figure>",
    f'<div class="testimonial-item"><div>{QUOTE}</div><div>Phil Probe</div><div>Founder</div></div>',
    # The same people without any quotation nearby: the other company gives them away.
    card("Raphael Probe", "CEO, Othergem"),
    card("Margot Probe", "Co-Founder &amp; COO, OTHERLUX"),
    "<p>Dr. Toby Probe , Otherix CEO</p>",
    card("Marc Probe", ", CEO, Other Fuels", "span", "span"),
    # Somebody who works for the founder is not the founder.
    card("Anika Probe", "Personal Assistant to the Founder &amp; CEO"),
])
def test_testimonials_and_other_companies_are_rejected(body):
    assert names(body) == []


def test_a_quote_elsewhere_on_the_page_does_not_hide_the_team():
    filler = "<p>" + "We build inspection robots for warehouses and factories. " * 20 + "</p>"
    body = (f"<section><div>{QUOTE}</div><div>Phil Probe</div><div>Founder, Otherco</div></section>"
            f"<section>{filler}<h2>Our team</h2>" + card("Anna Muster", "Co-Founder &amp; CEO") + "</section>")
    assert names(body) == [("Anna Muster", "Co-Founder")]
