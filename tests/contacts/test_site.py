import pytest

from kaltstart.contacts.site import (
    links, on_company_domain, profile_on_another_site, same_site, site_host,
    visible_text)


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


@pytest.mark.parametrize("website,name,expected", [
    # A profile of the company on an accelerator's or a directory's site.
    ("https://www.example.com/qubit-robotics-systems", "Qubit Robotics", True),
    ("https://example.com/startups/qubit", "Qubit AG", True),
    # The company's own site, with or without a path.
    ("https://example-robotics.ch", "Example Robotics", False),
    ("https://www.examplerobotics.com/en/example-robotics", "Example Robotics", False),
    ("https://example.ch/en", "Example Robotics", False),
    # One word of the name in the host is enough to be its own site.
    ("https://example.com/example-robotics", "Example Robotics", False),
    ("https://example.ch/de/robotics", "Other Name", False),
    # Too short a name to tell.
    ("https://example.com/ab", "AB", False),
])
def test_profile_on_another_site(website, name, expected):
    assert profile_on_another_site(website, name) is expected
