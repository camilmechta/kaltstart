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


# Final review of the privacy page: every sentence must match what the app does.
def test_the_page_says_what_kept_mails_and_typed_names_hold(client):
    page = client.get("/privacy").text
    for words in ("whether you attach a CV", "with their status and dates",
                  "when your invitation code was used",
                  "A student may also type a name",
                  "stay in that mail until you ask",
                  "a fingerprint of your name"):
        assert words in page, words
    assert "Nothing comes from social networks or other websites" not in page


def test_the_page_describes_the_cookie_and_the_ip_counting(client):
    page = client.get("/privacy").text
    for words in ("protects forms", "14 days after your last visit",
                  "kept in your browser", "IP address is counted in memory",
                  "Cloudflare"):
        assert words in page, words


def test_the_page_mentions_the_sign_in_logs_of_supabase(client):
    assert "Supabase, which handles sign-in, keeps its own technical logs" in client.get("/privacy").text


def test_the_page_mentions_the_address_a_student_gives(client):
    page = client.get("/privacy").text
    assert "A student may also type a name or an address they found themselves" in page
    assert "Kaltstart never guesses an address" in page


def test_the_page_mentions_linkedin(client):
    page = client.get("/privacy").text
    assert "For a LinkedIn message, Kaltstart keeps the texts and the person's name, as for a mail; it never visits LinkedIn." in page.replace("&#39;", "'")
