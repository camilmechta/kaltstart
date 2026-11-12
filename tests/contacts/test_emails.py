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
    ('<a href="mailto:%69nfo@example.ch">Mail</a>', ["info@example.ch"]),
    ('<a href="mailto:a@example.ch,b@example.ch">Mail</a>', ["a@example.ch", "b@example.ch"]),
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
    # Bare words are never an address: a title or heading must not become one.
    "<p>hello at example dot ch</p>",
    "<p>We meet at example dot ch every week</p>",
    "<p>See you at example.ch tomorrow</p>",
    "<h1>Life at Example.ch</h1>",
    "<p>Careers at example.ch</p>",
    "<p>Contact (at) Example.ch office</p>",          # capitalised prose, not an address
    "<p>Jobs [at] Example.ch</p>",
    "<script>var m='hidden@example.ch'</script>",
])
def test_noise_is_discarded(body):
    assert extract_addresses(page(body), ["example.ch"]) == ([], 0)


def test_invented_contact_page_fixture():
    html = (FIXTURES / "contact_page.html").read_text(encoding="utf-8")
    found = extract_addresses(Page("https://example.ch/kontakt", "contact", html), ["example.ch"])
    assert found == (["hello@example.ch", "jobs@example.ch"], 0)


def test_page_title_never_becomes_an_address():
    html = "<html><head><title>Jobs at Example.ch</title></head><body><h1>Jobs at Example.ch</h1></body></html>"
    assert extract_addresses(Page("https://example.ch/jobs", "careers", html), ["example.ch"]) == ([], 0)


def cloudflare(address, key=0x42):
    """Encode an address the way Cloudflare's email protection does."""
    return f"{key:02x}" + "".join(f"{ord(char) ^ key:02x}" for char in address)


@pytest.mark.parametrize("body", [
    '<a href="/cdn-cgi/l/email-protection#{code}">[email&#160;protected]</a>',
    '<span class="__cf_email__" data-cfemail="{code}">[email&#160;protected]</span>',
    '<a href="/cdn-cgi/l/email-protection#{code}"><span class="__cf_email__" data-cfemail="{code}">[email&#160;protected]</span></a>',
])
def test_cloudflare_protected_addresses_are_decoded(body):
    html = body.format(code=cloudflare("support@example.ch"))
    assert extract_addresses(page(html), ["example.ch"]) == (["support@example.ch"], 0)


def test_broken_cloudflare_code_is_ignored():
    html = '<span class="__cf_email__" data-cfemail="zz12">x</span><a href="/cdn-cgi/l/email-protection#4">y</a>'
    assert extract_addresses(page(html), ["example.ch"]) == ([], 0)
