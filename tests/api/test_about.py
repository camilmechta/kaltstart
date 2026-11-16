from tests.api.conftest import REMOVAL, sign_up_and_in
from tests.api.test_company_page import client, ready, store  # noqa: F401  (fixtures)


def test_the_about_page_is_public_and_credits_the_source(client):
    page = client.get("/about")
    assert page.status_code == 200
    for words in ("Tech.eu Funding Explorer", "CC BY 4.0", "own website", "never sends",
                  "r@example.com"):
        assert words in page.text, words


def test_tech_eu_is_not_repeated_on_every_page(client):
    ready(client)
    for path in ("/companies", "/companies/c1", "/profile", "/mails"):
        page = client.get(path).text
        assert "Tech.eu" not in page, path
        assert 'href="/about"' in page, path
