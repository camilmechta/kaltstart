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
    card("Mia Probe", "Hardware Engineer"),
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


# Found by the review: a job opening has the shape of a team card.
@pytest.mark.parametrize("body", [
    '<a class="job"><div>Head of Sales</div><div>Full Time</div></a>',
    '<div class="job"><h4>Product Manager</h4><p>Apply Now</p></div>',
    "<li><h4>Head of Product</h4><p>Hybrid Remote</p></li>",
    "<div><div>Head of Marketing</div><div>Vollzeit Zürich</div></div>",
    "<div><div>Zurich Switzerland</div><div>Product Manager</div></div>",
    "<div><div>Permanent Position</div><div>Head of Data</div></div>",
    "<div><div>Festanstellung Vollzeit</div><div>Vertriebsleiter (m/w/d)</div></div>",
    "<div><div>Basel Stadt</div><div>Head of Sales</div></div>",
    "<div><div>New York</div><div>Sales Director</div></div>",
    "<div><div>Open Positions</div><div>Head of Product 80-100%</div></div>",
    # A product feature, a section heading, a customer page.
    "<div><h3>Smart Reporting</h3><p>Built for every Head of Sales</p></div>",
    "<div><div>Customer Stories</div><div>Sales Manager</div></div>",
    # A heading that is a title, above a name, announces something else.
    "<div><h3>CEO</h3><p>Jonas von Beispiel</p></div>",
    # A whole neighbouring card is not a name.
    '<div><div class="card"><h4>Anna Muster</h4><p>Developer</p></div>'
    '<div class="card"><p>Head of Sales</p></div></div>',
])
def test_job_openings_and_headings_are_not_people(body):
    for kind in ("home", "team"):
        assert names(body, kind=kind) == []


@pytest.mark.parametrize("heading", [
    "Advisors", "Advisory Board", "Board of Directors", "Verwaltungsrat", "Our Investors",
    "Open positions", "Offene Stellen", "What our customers say", "Speakers",
])
def test_cards_under_a_section_that_is_not_the_team_are_skipped(heading):
    body = f"<section><h2>{heading}</h2>" + card("Ben Probe", "Chief Marketing Officer") + "</section>"
    assert names(body) == []


def test_cards_under_a_team_heading_are_read():
    body = ("<section><h2>Advisors</h2>" + card("Ben Probe", "Chief Marketing Officer") + "</section>"
            "<section><h2>Leadership team</h2>" + card("Anna Muster", "Co-Founder &amp; CEO", "h3", "p")
            + card("Clara Vorlage", "Head of Product", "h3", "p") + "</section>")
    assert names(body) == [("Anna Muster", "Co-Founder & CEO"), ("Clara Vorlage", "Head of Product")]


def test_a_team_card_whose_classes_say_position_or_job_title_is_read():
    # Seen on a real site: the title block of a team card is classed "team__position".
    body = ('<div class="card"><h3>Gregor Entwurf</h3>'
            '<p class="cl-team__position">Founder - CEO/CTO</p></div>'
            '<div class="card"><div><h3>Jean Probe</h3></div>'
            '<p class="job-title">CEO @Example Robotics</p></div>')
    assert names(body) == [("Gregor Entwurf", "Founder - CEO/CTO"),
                           ("Jean Probe", "CEO @Example Robotics")]


@pytest.mark.parametrize("wrapper", ["jobs-list", "career-teaser", "open-positions offene-stellen",
                                     "job-listing", "vacancies"])
def test_cards_inside_a_job_listing_are_skipped(wrapper):
    body = f'<div class="{wrapper}">' + card("Ben Probe", "Head of Sales") + "</div>"
    assert names(body) == []


def test_a_title_written_above_the_name_in_the_same_card_is_read():
    # Seen on two real sites: the title first, the name as a heading right after.
    body = ('<article><div><img alt=""></div><div><p>Co-founder and CEO</p><h3>Anna Muster</h3>'
            '<span>Two exits. On a mission to make robots count.</span></div></article>'
            '<article><div><img alt=""></div><div><p>Co-founder and CTO</p><h3>Peter Beispiel</h3>'
            '<span>Tech lover and tinkerer.</span></div></article>')
    assert names(body) == [("Anna Muster", "Co-founder and CEO"),
                           ("Peter Beispiel", "Co-founder and CTO")]


def test_a_name_before_the_title_wins_over_the_name_after_it():
    body = "<div><h3>Anna Muster</h3><p>CEO</p><h3>Peter Beispiel</h3><p>CTO</p></div>"
    assert names(body) == [("Anna Muster", "CEO"), ("Peter Beispiel", "CTO")]


def test_a_few_quoted_words_in_a_biography_are_not_a_testimonial():
    body = ('<div><h3>Anna Muster, PhD</h3><p>CEO &amp; Co-Founder</p>'
            '<div><p>Teaches at a summer school, named “Rising Star in Robotics,” and '
            'a former engineer.</p></div></div>')
    assert names(body) == [("Anna Muster", "CEO & Co-Founder")]


def test_the_title_is_the_first_line_of_a_block_with_line_breaks():
    body = ('<div><h3><a href="/a">Anna Muster, PhD</a></h3>'
            '<div>Co-Founder &amp; CEO<br>economist, entrepreneur and expert in innovation<br>'
            'and technology development.<br><a href="/x">Profile</a></div></div>')
    assert names(body) == [("Anna Muster", "Co-Founder & CEO")]


def test_a_name_three_wrappers_above_the_title_is_read():
    body = ('<div><div><div><h6>Anna Muster</h6></div></div>'
            '<div><div class="variant"><div><p>Co-Founder &amp; CEO</p></div></div>'
            '<div class="variant"><div><p>Co-Founder &amp; CEO</p></div></div></div></div>')
    assert names(body) == [("Anna Muster", "Co-Founder & CEO")]


@pytest.mark.parametrize("hidden", [
    'class="w-condition-invisible"', 'style="display:none"', 'style="color: red; display: none;"',
])
def test_text_the_site_hides_is_not_read(hidden):
    # Seen on a real site: every card carries "Co-founder", hidden for those who are not.
    body = ('<div><div><h3>Anna Muster</h3></div><p>Co-founder</p><p>Chief Executive Officer</p></div>'
            f'<div><div><h3>Ben Probe</h3></div><p {hidden}>Co-founder</p><p>Senior Scientist</p></div>')
    assert names(body) == [("Anna Muster", "Co-founder")]


def test_people_behind_a_tab_or_a_filter_are_read():
    # Seen on a real site: the second department of a team grid carries "hidden".
    body = ('<article><h3>Anna Muster</h3><p>Co-Founder &amp; CEO</p></article>'
            '<article hidden><h3>Clara Vorlage</h3><p>Senior Product Manager</p></article>'
            '<article aria-hidden="true"><h3>Ben Probe</h3><p>Head of Sales</p></article>')
    assert [name for name, _title in names(body)] == ["Anna Muster", "Clara Vorlage", "Ben Probe"]


def test_co_founder_written_in_two_words():
    body = "<div><div>Co Founder</div><h2>Peter Beispiel</h2></div>"
    assert names(body) == [("Peter Beispiel", "Co Founder")]


def test_a_long_block_is_read_for_its_first_line():
    body = ('<div><h3>Peter Beispiel, PhD</h3><div>Co-Founder &amp; CTO<br>Chemist, entrepreneur '
            'and expert in machine learning for materials discovery,<br>software design, and '
            'autonomous experimentation.<br><a href="/x">Profile</a> – <a href="/y">Papers</a>'
            '</div></div>')
    assert names(body) == [("Peter Beispiel", "Co-Founder & CTO")]


def test_a_team_card_with_a_logo_and_no_statement_is_read():
    body = ('<section><p>We are a small team that loves robots and warehouses alike.</p>'
            '<div><div class="card"><img alt="Team picture"><div><div>Anna Muster</div>'
            '<div>Managing Director</div></div><img alt="Author Logo" class="author-logo"></div></div>'
            '</section>')
    assert names(body) == [("Anna Muster", "Managing Director")]


@pytest.mark.parametrize("body", [
    # Job titles of the customers a product is for, not people.
    "<div><div>Finance</div><div>Direttore Finanziario (CFO) · Responsabile Amministrativo</div></div>",
    "<div><div>Direttore Generale</div><div>CEO</div></div>",
    "<div><div>Responsabile Vendite</div><div>Head of Sales</div></div>",
])
def test_job_titles_in_another_language_are_not_names(body):
    assert names(body, kind="home") == []


@pytest.mark.parametrize("logo", [
    '<img alt="Other Group Logo" src="/a.png">', '<img alt="" class="client-logo" src="/a.png">',
])
def test_a_card_with_a_logo_is_a_customer_speaking(logo):
    # Seen on a real site: a testimonial without quotation marks, signed with the customer's logo.
    body = ('<div><div><p><strong>Ben Probe, CEO</strong></p></div>'
            '<div><p>Their tools changed the way we run our operations.</p></div>'
            f'<div><div>{logo}</div></div></div>')
    assert names(body, kind="home") == []


def test_a_plain_label_announces_a_board_like_a_heading():
    # Seen on a real site: "Board" written in a paragraph, not in a heading.
    body = ("<section><h2>Who builds it</h2>"
            "<p>Leadership</p><div>" + card("Anna Muster", "Co-Founder &amp; CEO") + "</div>"
            "<p>Board</p><div>" + card("Ben Probe", "CEO &amp; Co-Founder") + "</div></section>")
    assert names(body) == [("Anna Muster", "Co-Founder & CEO")]


@pytest.mark.parametrize("label", ["Advisors", "Our Investors", "Advisory Board"])
def test_other_plain_labels_outside_the_team(label):
    body = f"<div><p>{label}</p><div>" + card("Ben Probe", "Chief Marketing Officer") + "</div></div>"
    assert names(body) == []


def test_a_row_of_tabs_is_not_a_section_label():
    # "Team | Board" above one grid: the grid shows the team first.
    body = ("<div><span>Team</span><span>Board</span><div>"
            + card("Anna Muster", "Co-Founder &amp; CEO") + "</div></div>")
    assert names(body) == [("Anna Muster", "Co-Founder & CEO")]


def test_a_label_inside_the_card_is_not_a_section_label():
    body = "<div><div>Board</div><div>Anna Muster</div><div>Chairwoman &amp; CEO</div></div>"
    assert names(body) == [("Anna Muster", "Chairwoman & CEO")]


@pytest.mark.parametrize("href", [
    "/success-stories/faster-warehouses", "/case-studies/other-group",
    "https://example.ch/customers/other-group", "/kunden/other-group", "/referenzen/other"])
def test_a_card_that_links_to_a_customer_story_is_a_customer(href):
    # Seen on a real site: no quotation, a logo, and the card leads to the story.
    body = (f'<a href="{href}"><div><img class="story-logo" src="/a.png">'
            '<div><p>Ben Probe</p><p>Chief Executive Officer</p></div></div>'
            '<p>Faster warehouses</p><p>Other Group</p></a>')
    assert names(body, kind="home") == []


def test_a_team_card_that_links_to_a_profile_is_read():
    body = ('<a href="/team/anna-muster"><div><p>Anna Muster</p>'
            '<p>Chief Executive Officer</p></div></a>')
    assert names(body) == [("Anna Muster", "Chief Executive Officer")]


@pytest.mark.parametrize("line", [
    "With Anna Muster, CEO of Example Robotics.",       # seen on a real site: a video caption
    "Mit Anna Muster, CEO von Example Robotics",
    "By Anna Muster, Founder", "Interview Anna Muster, Founder",
])
def test_a_caption_that_introduces_somebody_is_not_a_name(line):
    assert names(f"<div><h4>How we build robots</h4><p><strong>{line}</strong></p></div>",
                 kind="home") == []


def test_a_degree_and_a_school_before_the_name_are_not_part_of_it():
    assert names(card("MSc ETH Lina Beispiel", "Co-Founder, Chief Executive Officer")) == [
        ("Lina Beispiel", "Co-Founder, Chief Executive Officer")]


def test_a_question_read_as_a_name_is_dropped():
    assert names("<p>Was Einkauf, Technik und Geschäftsführung wissen wollen.</p>") == []


def test_a_long_run_of_credentials_is_read_in_linear_time():
    # A run of ",MBA" that does not end the line made the credential regex
    # backtrack through 2**n paths: 24 of them took seconds, 40 would hang.
    import time
    body = "<p>Gründer Anna Muster" + ",MBA" * 24 + "x</p>"
    start = time.monotonic()
    names(body, kind="home")
    assert time.monotonic() - start < 0.5


# The new technical words must not turn a name into a title (technical roles plan, Task 2).
@pytest.mark.parametrize("body,expected", [
    (card("Ai Beispiel", "Head of Product"), [("Ai Beispiel", "Head of Product")]),
    (card("Mia Probe", "Head of R&amp;D"), [("Mia Probe", "Head of R&D")]),
    (card("Tim Muster", "VP Engineering"), [("Tim Muster", "VP Engineering")]),
])
def test_technical_heads_on_a_team_page(body, expected):
    assert names(body) == expected


# Final review of the technical roles: "AI" and "ML" in capitals are title
# words, not another organisation's name.
@pytest.mark.parametrize("text,categories", [
    ("CTO & Head of AI", ("leadership", "engineering")),
    ("Founder & Head of AI", ("leadership", "engineering")),
    ("CTO and Head of AI", ("leadership", "engineering")),
    ("CTO / Head of AI", ("leadership", "engineering")),
    ("CTO & ML Lead", ("leadership", "engineering")),
])
def test_a_leader_who_also_leads_ai_is_kept(text, categories):
    from kaltstart.contacts.people import _own_title
    title = _own_title(text, "example")
    assert title is not None and title.categories == categories
