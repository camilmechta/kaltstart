from kaltstart.contacts.pages import FALLBACK_PATHS, KEYWORDS, KINDS, choose_links

HOME = "https://example.ch/"
HOSTS = ["example.ch"]


def home(*anchors):
    return "<html><body>" + "".join(anchors) + "</body></html>"


def a(href, text="link"):
    return f'<a href="{href}">{text}</a>'


def test_constants_match_the_spec():
    assert KINDS == ("legal", "contact", "team", "careers")
    assert KEYWORDS["legal"] == ("impressum", "imprint", "legal")
    assert KEYWORDS["contact"] == ("contact", "kontakt")
    assert KEYWORDS["team"] == ("team", "about", "ueber-uns", "über uns",
                                "about-us", "company", "unternehmen")
    assert KEYWORDS["careers"] == ("careers", "career", "jobs", "karriere", "join")


def test_priority_order_and_kinds():
    html = home(a("/jobs"), a("/team"), a("/kontakt"), a("/impressum"))
    assert choose_links(html, HOME, HOSTS) == [
        ("https://example.ch/impressum", "legal"),
        ("https://example.ch/kontakt", "contact"),
        ("https://example.ch/team", "team"),
        ("https://example.ch/jobs", "careers"),
    ]


def test_keyword_matches_link_text_or_url_case_insensitively():
    html = home(a("/p/42", "Über uns"), a("/KARRIERE", "Work"))
    assert choose_links(html, HOME, HOSTS) == [
        ("https://example.ch/p/42", "team"),
        ("https://example.ch/KARRIERE", "careers"),
    ]


def test_at_most_two_per_kind():
    html = home(a("/contact"), a("/contact/sales"), a("/contact/press"))
    assert choose_links(html, HOME, HOSTS) == [
        ("https://example.ch/contact", "contact"),
        ("https://example.ch/contact/sales", "contact"),
    ]


def test_at_most_seven_in_total():
    anchors = [a(f"/{word}/{i}") for word in ("impressum", "kontakt", "team", "jobs")
               for i in range(3)]
    chosen = choose_links(home(*anchors), HOME, HOSTS)
    assert len(chosen) == 7
    assert [kind for _, kind in chosen] == [
        "legal", "legal", "contact", "contact", "team", "team", "careers"]


def test_only_same_site_html_pages():
    html = home(
        a("mailto:jobs@example.ch", "Jobs"),
        a("tel:+41000000", "Contact"),
        a("javascript:void(0)", "Team"),
        a("https://www.linkedin.com/company/x", "About us on LinkedIn"),
        a("/team.pdf", "Team"),
        a("/team.jpg", "Team"),
        a("https://example.ch/", "Company"),
        a("https://example.ch", "Company"),
        a("team/", "Team"),
    )
    assert choose_links(html, HOME, HOSTS) == [("https://example.ch/team/", "team")]


def test_duplicate_urls_are_returned_once():
    html = home(a("/team"), a("/team#founders"), a("/team"))
    assert choose_links(html, HOME, HOSTS) == [("https://example.ch/team", "team")]


def test_fallback_paths_when_no_link_matches():
    html = home(a("/product"), a("/pricing"))
    assert choose_links(html, HOME, HOSTS) == [
        ("https://example.ch" + path, kind) for path, kind in FALLBACK_PATHS]
    assert FALLBACK_PATHS == (
        ("/impressum", "legal"), ("/imprint", "legal"), ("/contact", "contact"),
        ("/team", "team"), ("/about", "team"), ("/careers", "careers"),
        ("/jobs", "careers"))


def test_legal_notice_is_preferred_over_privacy_and_terms_pages():
    html = home(a("/legal/privacy", "Privacy & Legal"), a("/legal/terms", "Legal terms"),
                a("/datenschutz", "Datenschutz"), a("/impressum", "Impressum"),
                a("/legal", "Legal"))
    assert choose_links(html, HOME, HOSTS) == [
        ("https://example.ch/impressum", "legal"),
        ("https://example.ch/legal", "legal"),
    ]


def test_same_page_under_two_spellings_takes_one_slot():
    html = home(a("/team"), a("/team/"), a("/contact?ref=nav"), a("/contact"))
    assert choose_links(html, HOME, HOSTS) == [
        ("https://example.ch/contact?ref=nav", "contact"),
        ("https://example.ch/team", "team"),
    ]


def test_keywords_match_whole_words_only():
    html = home(a("/blog/joint-venture", "News"), a("/teamwork-tips", "Blog"),
                a("/join-us", "Work with us"))
    assert choose_links(html, HOME, HOSTS) == [("https://example.ch/join-us", "careers")]


def test_home_page_variants_are_never_chosen():
    html = home(a("/?lang=en", "Company"), a("https://www.example.ch/", "About"), a("/team"))
    assert choose_links(html, HOME, HOSTS) == [("https://example.ch/team", "team")]
