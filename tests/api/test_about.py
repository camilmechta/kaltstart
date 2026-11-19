from tests.api.conftest import REMOVAL, sign_up_and_in
from tests.api.test_company_page import client, ready, store  # noqa: F401  (fixtures)


def test_the_about_page_is_public_and_credits_the_source(client):
    page = client.get("/about")
    assert page.status_code == 200
    for words in ("Tech.eu Funding Explorer", "CC BY 4.0", "own website", "Your part",
                  "r@example.com"):
        assert words in page.text, words


def test_tech_eu_is_not_repeated_on_every_page(client):
    ready(client)
    for path in ("/companies", "/companies/c1", "/profile", "/mails"):
        page = client.get(path).text
        assert "Tech.eu" not in page, path
        assert 'href="/about"' in page, path


def test_the_about_page_does_not_repeat_the_steps(client):
    page = client.get("/about").text
    assert "How it works" not in page and "the part that gets you hired is yours" in page


def test_the_about_page_says_how_many_mails_a_student_can_keep(client):
    assert ("You can keep up to 10 mails a week, 5 waiting at a time, "
            "and write to each company once.") in client.get("/about").text
