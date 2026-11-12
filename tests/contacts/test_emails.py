from pathlib import Path

import pytest

from kaltstart.contacts.emails import extract_addresses
from kaltstart.contacts.models import Page

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sites"


def page(body):
    return Page("https://example.ch/kontakt", "contact", f"<html><body>{body}</body></html>")


@pytest.mark.parametrize("body,expected", [
    ('<a href="mailto:Hello@Example.ch?subject=Hi">Mail</a>', ["hello@example.ch"]),
    ("<p>Write to jobs@example.ch.</p>", ["jobs@example.ch"]),
    ("<p>hello [at] example.ch</p>", ["hello@example.ch"]),
    ("<p>hello(at)example.ch</p>", ["hello@example.ch"]),
    ("<p>hello at example dot ch</p>", ["hello@example.ch"]),
    ("<p>hello [at] example [dot] ch</p>", ["hello@example.ch"]),
    ("<p>info@example.ch and info@example.ch</p>", ["info@example.ch"]),
    ("<p>anna.muster@mail.example.ch</p>", ["anna.muster@mail.example.ch"]),
])
def test_addresses_on_the_company_domain(body, expected):
    assert extract_addresses(page(body), ["example.ch"]) == (expected, 0)


def test_other_domains_are_counted_not_kept():
    body = "<p>info@example.ch, press@agency.example.com, x@agency.example.com</p>"
    assert extract_addresses(page(body), ["example.ch"]) == (["info@example.ch"], 2)


@pytest.mark.parametrize("body", [
    "<p>logo@2x.png</p>",
    "<p>abc123@sentry.io</p>",
    "<p>team@wixpress.com</p>",
    "<p>id@o1234.ingest.sentry.io</p>",
    "<p>We meet at example dot ch every week</p>",   # bare words inside a sentence
    "<p>See you at example.ch tomorrow</p>",
    "<script>var m='hidden@example.ch'</script>",
])
def test_noise_is_discarded(body):
    assert extract_addresses(page(body), ["example.ch"]) == ([], 0)


def test_invented_contact_page_fixture():
    html = (FIXTURES / "contact_page.html").read_text(encoding="utf-8")
    found = extract_addresses(Page("https://example.ch/kontakt", "contact", html), ["example.ch"])
    assert found == (["hello@example.ch", "jobs@example.ch"], 0)
