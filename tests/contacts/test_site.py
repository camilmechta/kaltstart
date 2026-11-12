import pytest

from kaltstart.contacts.site import (
    links, on_company_domain, same_site, site_host, visible_text)


@pytest.mark.parametrize("website,expected", [
    ("https://www.Example.ch/", "example.ch"),
    ("https://example.ch/en/home", "example.ch"),
    ("app.example.ch", "app.example.ch"),
    ("HTTP://EXAMPLE.DE", "example.de"),
])
def test_site_host(website, expected):
    assert site_host(website) == expected


@pytest.mark.parametrize("url,expected", [
    ("https://example.ch/team", True),
    ("https://www.example.ch/team", True),
    ("https://jobs.example.ch/", True),
    ("https://example.com/team", False),
    ("https://notexample.ch/", False),
    ("https://www.linkedin.com/company/example", False),
])
def test_same_site(url, expected):
    assert same_site(url, ["example.ch"]) is expected


@pytest.mark.parametrize("domain,hosts,expected", [
    ("example.ch", ["example.ch"], True),
    ("mail.example.ch", ["example.ch"], True),
    ("example.ch", ["app.example.ch"], True),     # parent of a generic subdomain
    ("example.ch", ["shop.example.ch"], True),
    ("ethz.ch", ["startup.ethz.ch"], False),      # a host's parent may be a third party
    ("webflow.io", ["startup.webflow.io"], False),
    ("co.uk", ["startup.co.uk"], False),
    ("ch", ["app.example.ch"], False),            # a bare suffix is never a company domain
    ("example.com", ["example.ch", "example.com"], True),
    ("gmail.com", ["example.ch"], False),
])
def test_on_company_domain(domain, hosts, expected):
    assert on_company_domain(domain, hosts) is expected


def test_visible_text_drops_scripts_and_collapses_whitespace():
    html = ("<html><head><style>p{}</style></head><body><script>var a=1</script>"
            "<p>Hello\n  world</p></body></html>")
    assert visible_text(html) == "Hello world"


def test_links_are_absolute_in_order_without_fragments():
    html = '<a href="/team#top">Team</a><a href="https://example.com/x">X</a><a>no href</a>'
    assert links(html, "https://example.ch/") == [
        ("https://example.ch/team", "Team"), ("https://example.com/x", "X")]
