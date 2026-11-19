"""The privacy page (privacy page design, 2026-11-19)."""

from kaltstart.api.session import COOKIE_DAYS
from kaltstart.api.store import RECENT_ROUND_DAYS
from tests.api.test_company_page import client, ready, store  # noqa: F401  (fixtures)


def test_the_privacy_page_is_public(client):
    page = client.get("/privacy")
    assert page.status_code == 200
    for words in ("r@example.com", "Render", "Frankfurt", "Supabase", "Paris",
                  "never sends", "When the project ends"):
        assert words in page.text, words


def test_the_page_matches_the_code(client):
    page = client.get("/privacy").text
    assert COOKIE_DAYS == 14 and "14 days" in page
    assert RECENT_ROUND_DAYS == 365 and "12 months" in page


def test_every_page_links_to_privacy(client):
    for path in ("/", "/about", "/signin", "/signup"):
        assert 'href="/privacy"' in client.get(path).text, path
    ready(client)
    for path in ("/companies", "/profile", "/mails"):
        assert 'href="/privacy"' in client.get(path).text, path


def test_the_signup_page_explains_the_data_use(client):
    assert "How Kaltstart uses your data" in client.get("/signup").text


def test_a_signed_in_student_can_read_it(client):
    ready(client)
    assert client.get("/privacy").status_code == 200
