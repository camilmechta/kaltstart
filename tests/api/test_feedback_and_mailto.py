"""Beta additions (D109): a feedback link on every page, and a button that
opens the kept mail in the student's own mail app, filled in."""

import re

import pytest

from kaltstart.api.app import mailto_link
from tests.api.conftest import csrf, sign_up_and_in, user_id
from tests.api.test_mails import keep


FEEDBACK = 'href="mailto:removal@example.com?subject=Kaltstart%20feedback"'


@pytest.mark.parametrize("path", ["/", "/about", "/privacy", "/signin", "/signup"])
def test_every_public_page_has_the_feedback_link(client, path):
    assert FEEDBACK in client.get(path).text


def test_signed_in_pages_have_the_feedback_link(client, store, auth):
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    for path in ("/companies", "/companies/dev01", "/mails", f"/mails/{mail_id}", "/profile"):
        assert FEEDBACK in client.get(path).text, path


def test_the_mailto_link_encodes_every_part():
    link = mailto_link("info@novalearn.example.de", "Hi & bye? 100%", "Hi Anna!\n\nLine two.")
    assert link == ("mailto:info@novalearn.example.de?subject=Hi%20%26%20bye%3F%20100%25"
                    "&body=Hi%20Anna%21%0D%0A%0D%0ALine%20two.")


@pytest.mark.parametrize("address", [None, "", "no-at-sign", "a@b.ch,c@d.ch", "a@b.ch?cc=x@y.ch",
                                     "a b@c.ch", "a@b.ch\nBcc: x@y.ch", "a@b.ch;c@d.ch",
                                     "<a@b.ch>", "a@b.ch&body=x", "a@b@c.ch", "a%40b.ch"])
def test_no_link_for_an_address_that_is_not_exactly_one_address(address):
    assert mailto_link(address, "Subject", "Body") is None


def test_the_mail_page_offers_to_open_the_mail_app(client, store, auth):
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    page = client.get(f"/mails/{mail_id}").text
    button = re.search(r'<a [^>]*data-mail-app[^>]*>', page).group(0)
    assert 'href="mailto:info@novalearn.example.de?subject=Nova%20Learn%20internship%3F' in button
    assert "&amp;body=Hi%20Anna%21%0D%0A%0D%0ACongrats%20on%20your%20round." in button
    assert 'data-copied-form="copied-form"' in button
    assert "Open in my mail app" in page
    assert page.count("data-copy=") == 3            # the copy buttons stay


def test_a_linkedin_or_removed_mail_has_no_mail_app_button(client, store, auth):
    from dataclasses import replace
    sign_up_and_in(client)
    me = user_id(auth)
    linkedin, removed = keep(store, me, "dev01"), keep(store, me, "dev02")
    for index, m in enumerate(store._mails):
        if m.id == linkedin:
            store._mails[index] = replace(m, address_type="linkedin", address=None)
        if m.id == removed:
            store._mails[index] = replace(m, redacted=True, address=None, subject=None, body=None)
    for mail_id in (linkedin, removed):
        assert "data-mail-app" not in client.get(f"/mails/{mail_id}").text, mail_id


def test_the_script_marks_the_mail_copied_when_the_mail_app_opens():
    from pathlib import Path
    script = (Path(__file__).parents[2] / "src" / "kaltstart" / "api" / "static" / "app.js").read_text()
    assert "data-mail-app" in script
