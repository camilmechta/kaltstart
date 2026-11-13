from pathlib import Path

import pytest

from kaltstart.contacts.models import Page
from kaltstart.contacts.people import extract_people

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sites"
COMPANY = "Example Robotics"


def names(body, kind="team", company=COMPANY):
    page = Page("https://example.ch/team", kind, f"<html><body>{body}</body></html>")
    return [(p.name, p.title) for p in extract_people(page, company)]


def card(name, title, name_tag="div", title_tag="div"):
    return f"<div><{name_tag}>{name}</{name_tag}><{title_tag}>{title}</{title_tag}></div>"


@pytest.mark.parametrize("body,expected", [
    ("<p>Geschäftsführer: Anna Muster</p>", [("Anna Muster", "Geschäftsführer")]),
    ("<p>Geschäftsführung / Geschäftsführer: Dr. Anna Muster, Jonas Beispiel</p>",
     [("Anna Muster", "Geschäftsführer"), ("Jonas Beispiel", "Geschäftsführer")]),
    ("<div><h3>Anna Muster</h3><p>Co-Founder &amp; CEO</p></div>", [("Anna Muster", "Co-Founder & CEO")]),
    ("<div><p>CEO</p><h3>Jonas von Beispiel</h3></div>", [("Jonas von Beispiel", "CEO")]),
    ("<p>Anna Muster, Founder</p>", [("Anna Muster", "Founder")]),
    ("<p>Gründerin Anna Maria Muster</p>", [("Anna Maria Muster", "Gründerin")]),
    # The label before a colon is never the name.
    ("<p>Vertretungsberechtigte Person: Dr. Anna Muster, Geschäftsführerin</p>",
     [("Anna Muster", "Geschäftsführerin")]),
    # Each label carries its own title.
    ("<p>CEO: Anna Muster, CTO: Peter Beispiel, Design: Clara Vorlage</p>",
     [("Anna Muster", "CEO"), ("Peter Beispiel", "CTO")]),
    ("<p>Anna Muster (CEO) and Peter Beispiel (Designer)</p>", [("Anna Muster", "CEO")]),
    ("<p>ANNA MUSTER, Founder</p>", [("Anna Muster", "Founder")]),
])
def test_names_next_to_a_title(body, expected):
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
    # Running prose is never read.
    "<p>Our CEO Anna Muster previously worked at Other Labs</p>",
    "<p>The core mechanism emerged from doctoral research at a university (Dr. Anna Muster, CEO).</p>",
])
def test_rejections(body):
    assert names(body) == []


def test_only_home_legal_and_team_pages_are_read():
    body = "<p>Anna Muster, Founder</p>"
    assert names(body, kind="careers") == []
    assert names(body, kind="contact") == []
    for kind in ("home", "legal", "team"):
        assert names(body, kind=kind) == [("Anna Muster", "Founder")]


def test_same_person_is_returned_once():
    assert names("<p>Anna Muster, Founder</p><p>CEO: Anna Muster</p>") == [("Anna Muster", "Founder")]


def test_source_url_is_the_page():
    page = Page("https://example.ch/impressum", "legal", "<p>Anna Muster, Founder</p>")
    assert extract_people(page, COMPANY)[0].source_url == "https://example.ch/impressum"


def test_invented_german_legal_notice():
    html = (FIXTURES / "impressum_de.html").read_text(encoding="utf-8")
    page = Page("https://example.de/impressum", "legal", html)
    assert [(p.name, p.title) for p in extract_people(page, "Beispiel Robotics")] == [
        ("Anna Muster", "Geschäftsführer"), ("Jonas Beispiel", "Geschäftsführer")]


def test_large_team_page_keeps_only_heads_and_managers():
    html = (FIXTURES / "team_cards.html").read_text(encoding="utf-8")
    page = Page("https://example.ch/team", "team", html)
    assert [(p.name, p.title, p.categories, p.level) for p in extract_people(page, COMPANY)] == [
        ("Anna Muster", "Co-Founder & CEO", ("leadership",), "head"),
        ("Jonas Beispiel", "Co-Founder & CTO", ("leadership",), "head"),
        ("Clara Vorlage", "Head of Product", ("product",), "head"),
        ("Mia Probe", "Product Manager", ("product",), "manager"),
        ("Noah Entwurf", "HR Manager", ("recruiting",), "manager"),
    ]


# Layouts seen on real team pages (first measurement), rebuilt with invented people.
@pytest.mark.parametrize("body,expected", [
    (card("Anna Muster", "Chief Executive Officer"), [("Anna Muster", "Chief Executive Officer")]),
    (card("Dr Jonas Beispiel", "Chief Technology Officer &amp; Co-Founder"),
     [("Jonas Beispiel", "Chief Technology Officer & Co-Founder")]),
    (card("Nico Vorlage, MRICS", "Co-Founder &amp; CCO", "h3", "p"), [("Nico Vorlage", "Co-Founder & CCO")]),
    (card("Prof Clara Stark", "Co-Founder, Advisor &amp; ETH Professor"),
     [("Clara Stark", "Co-Founder, Advisor & ETH Professor")]),
    (card("Nikita Probe", "Product Owner und Co-Founder"), [("Nikita Probe", "Product Owner und Co-Founder")]),
    (card("Gregor Entwurf", "Founder - CEO/CTO", "h3", "p"), [("Gregor Entwurf", "Founder - CEO/CTO")]),
    # The title names this very company.
    (card("Mia Vorlage", "Co-Founder Example Robotics, Sr. Investment Manager, Other Ventures"),
     [("Mia Vorlage", "Co-Founder Example Robotics, Sr. Investment Manager, Other Ventures")]),
    (card("Jean Probe", "CEO @Example Robotics", "div", "p"), [("Jean Probe", "CEO @Example Robotics")]),
    (card("Lukas Muster und Daniel Beispiel", "Gründer der Example Robotics AG", "b", "div"),
     [("Lukas Muster", "Gründer der Example Robotics AG"), ("Daniel Beispiel", "Gründer der Example Robotics AG")]),
    (card("Anna Muster", "CEO, Example Robotics"), [("Anna Muster", "CEO, Example Robotics")]),
    # Name and title on one line; credentials are not part of the title.
    ("<h2>Esmeralda Muster, MBA - CEO &amp; Co-Founder</h2>", [("Esmeralda Muster", "CEO & Co-Founder")]),
    ("<h2>ESMERALDA MUSTER, MBA CEO and Co-Founder</h2>", [("Esmeralda Muster", "CEO and Co-Founder")]),
    # The name is the neighbour of the title's wrapper, not of the title itself.
    ('<div class="member"><div>Leo Muster</div><div><p>Founder &amp; CEO​</p></div></div>',
     [("Leo Muster", "Founder & CEO")]),
    ("<div><h3>Dr. Donato Probe</h3><div><span>CEO &amp; Co-founder</span></div></div>",
     [("Donato Probe", "CEO & Co-founder")]),
    ("<div><div>Anna Muster</div><div><div></div><p>Co-founder</p></div></div>",
     [("Anna Muster", "Co-founder")]),
])
def test_real_layouts(body, expected):
    assert names(body) == expected


QUOTE = "“They cut our planning time in half and we would not go back to the old way.”"


@pytest.mark.parametrize("body", [
    # The title is held at another organisation.
    card("Petra Probe", "CEO at Other Works"),
    card("Petra Probe", "Board Member at Example Robotics, founder and former CEO of Other Fiber Company"),
    card("Petra Probe", "Board Member at Example Robotics, CEO at Other One, Ex-CEO at Third Co"),
    card("Nina Entwurf", "Textile Advisor &amp; Founder Other Fabrics Expo"),
    card("Hans Probe", "CEO Other Group (Family Office), Business Angel"),
    card("Raphael Probe", "CEO, Othergem"),
    card("Margot Probe", "Co-Founder &amp; COO, OTHERLUX"),
    "<p>Dr. Toby Probe , Otherix CEO</p>",
    card("Marc Probe", ", CEO, Other Fuels", "span", "span"),
    card("Mia Probe", "Head of Product, Other Works"),
    card("Mia Probe", "Head of Product at Other Works"),
    # The neighbouring block is not a person's name.
    card("Chief Technology Officer", "Co-Founder"),
    card("Example Robotics", "CEO", "h2", "p"),
    card("Other Capital Partners", "Founder"),
    "<ul><li>25+ years in micro-optics and photonics</li><li>Co-founder &amp; CTO, Other Optics (acquired)</li></ul>",
    "<ul><li>Technical Project Lead &amp; Co-founder, Other Light Labs (acquired by a group)</li></ul>",
    # Four testimonial layouts seen on real home pages.
    f'<figure class="slide"><p>{QUOTE}</p><div><p><span>Marc Probe</span><span>, CEO, Other Fuels</span></p></div></figure>',
    f"<div><div>{QUOTE}</div><div><div>Dr. Toby Probe , Otherix CEO</div></div></div>",
    f"<div><div>{QUOTE}</div><div><div><div>Raphael Probe</div><div>CEO, Othergem</div></div></div></div>",
    "<figure><blockquote>A quote without marks about the savings they made last year.</blockquote>"
    "<figcaption><div><span>Phil Probe</span><span>Founder</span></div></figcaption></figure>",
    f'<div class="testimonial-item"><div>{QUOTE}</div><div>Phil Probe</div><div>Founder</div></div>',
    # Somebody who works for the founder is not the founder.
    card("Anika Probe", "Personal Assistant to the Founder &amp; CEO"),
    # Titles that are not kept.
    card("Mia Probe", "Software Engineer"),
    card("Mia Probe", "Head of Engineering"),
    card("Mia Probe", "Account Manager"),
    card("Mia Probe", "Board Member"),
])
def test_people_not_kept(body):
    assert names(body) == []


def test_a_quote_elsewhere_on_the_page_does_not_hide_the_team():
    filler = "<p>" + "We build inspection robots for warehouses and factories. " * 20 + "</p>"
    body = (f"<section><div>{QUOTE}</div><div>Phil Probe</div><div>Founder, Otherco</div></section>"
            f"<section>{filler}<h2>Our team</h2>" + card("Anna Muster", "Co-Founder &amp; CEO") + "</section>")
    assert names(body) == [("Anna Muster", "Co-Founder & CEO")]


def test_without_a_company_name_any_organisation_in_the_title_rejects():
    assert names(card("Jean Probe", "CEO @Example Robotics"), company=None) == []
    assert names(card("Anna Muster", "Co-Founder &amp; CEO"), company=None) == [
        ("Anna Muster", "Co-Founder & CEO")]


@pytest.mark.parametrize("body,expected", [
    (card("Jonas Beispiel", "Head of Product"), [("Jonas Beispiel", "Head of Product", ("product",), "head")]),
    (card("Clara Vorlage", "Product Manager"), [("Clara Vorlage", "Product Manager", ("product",), "manager")]),
    (card("Mia Probe", "Head of People &amp; Culture"),
     [("Mia Probe", "Head of People & Culture", ("recruiting",), "head")]),
    (card("Anna Muster", "Co-Founder &amp; Head of Product"),
     [("Anna Muster", "Co-Founder & Head of Product", ("leadership", "product"), "head")]),
    ("<p>Leo Entwurf, Head of Sales</p>", [("Leo Entwurf", "Head of Sales", ("sales",), "head")]),
    (card("Noah Entwurf", "President &amp; CEO"), [("Noah Entwurf", "President & CEO", ("leadership",), "head")]),
])
def test_people_with_function_titles(body, expected):
    page = Page("https://example.ch/team", "team", f"<html><body>{body}</body></html>")
    assert [(p.name, p.title, p.categories, p.level)
            for p in extract_people(page, COMPANY)] == expected
