import pytest

from kaltstart.contacts.models import FetchOutcome, Page
from kaltstart.contacts.scrape import FAILURES, LITTLE_TEXT_CHARS, scrape_company

COMPANY = {"company_id": "c1", "name": "Example Robotics",
           "website": "https://example.ch", "size_category": "small"}
FILLER = "<p>" + "We build robots for warehouses. " * 10 + "</p>"
FORM = '<form><input name="name"><textarea name="message"></textarea></form>'


class FakeFetcher:
    def __init__(self, outcome=None, error=None):
        self.outcome, self.error = outcome, error

    def fetch_site(self, website):
        if self.error:
            raise self.error
        return self.outcome


def ok(*pages):
    return FetchOutcome("ok", tuple(pages), ("example.ch",))


def page(path, kind, body):
    return Page(f"https://example.ch{path}", kind, f"<html><body>{FILLER}{body}</body></html>")


def scrape(outcome=None, error=None):
    return scrape_company(COMPANY, FakeFetcher(outcome, error))


def test_constants():
    assert FAILURES == ("robots_forbidden", "unreachable", "little_text",
                        "other_domain_only", "contact_form_only", "no_address",
                        "not_own_site")
    assert LITTLE_TEXT_CHARS == 200


def test_result_with_contact():
    result = scrape(ok(
        page("/", "home", "<p>Welcome</p>"),
        page("/team", "team", "<p>Anna Muster, Founder</p><p>anna@example.ch</p>")))
    assert (result.company_id, result.name, result.website, result.size_category) == (
        "c1", "Example Robotics", "https://example.ch", "small")
    assert result.failure is None
    assert result.pages_fetched == ("https://example.ch/", "https://example.ch/team")
    assert [(e.address, e.type, e.source_url) for e in result.emails] == [
        ("anna@example.ch", "personal", "https://example.ch/team")]
    assert [(p.name, p.title, p.categories) for p in result.people] == [
        ("Anna Muster", "Founder", ("leadership",))]
    assert result.contact.address == "anna@example.ch"
    assert result.contact.person_name == "Anna Muster"
    assert result.contact.confidence == "high"


def test_address_is_typed_with_people_from_any_page():
    result = scrape(ok(
        page("/", "home", "<p>anna@example.ch</p>"),
        page("/impressum", "legal", "<p>Geschäftsführerin: Anna Muster</p>")))
    assert result.emails[0].type == "personal"


def test_address_seen_on_two_pages_is_kept_once():
    result = scrape(ok(
        page("/", "home", "<p>Info@example.ch</p>"),
        page("/kontakt", "contact", "<p>info@example.ch</p>")))
    assert [(e.address, e.source_url) for e in result.emails] == [
        ("info@example.ch", "https://example.ch/")]


def test_person_seen_on_two_pages_is_kept_once():
    result = scrape(ok(
        page("/team", "team", "<p>Anna Muster, Founder</p>"),
        page("/impressum", "legal", "<p>Geschäftsführerin: Anna Muster</p>")))
    assert [(p.name, p.source_url) for p in result.people] == [
        ("Anna Muster", "https://example.ch/team")]


@pytest.mark.parametrize("outcome,expected", [
    (FetchOutcome("robots_forbidden", (), ("example.ch",)), "robots_forbidden"),
    (FetchOutcome("unreachable", (), ("example.ch",)), "unreachable"),
    (ok(Page("https://example.ch/", "home", "<html><body><div id='app'></div></body></html>")),
     "little_text"),
    (ok(page("/", "home", "<p>press@agency.example.com</p>")), "other_domain_only"),
    (ok(page("/", "home", FORM)), "contact_form_only"),
    (ok(page("/", "home", "<p>Nothing here</p>")), "no_address"),
])
def test_failure_causes(outcome, expected):
    result = scrape(outcome)
    assert result.failure == expected
    assert result.contact is None
    assert result.emails == ()


def test_cause_priority():
    little = ok(Page("https://example.ch/", "home", f"<html><body>{FORM}</body></html>"))
    assert scrape(little).failure == "little_text"
    both = ok(page("/", "home", FORM + "<p>press@agency.example.com</p>"))
    assert scrape(both).failure == "other_domain_only"


def test_little_text_does_not_hide_a_found_address():
    tiny = ok(Page("https://example.ch/", "home", "<html><body>info@example.ch</body></html>"))
    result = scrape(tiny)
    assert result.failure is None
    assert result.emails[0].address == "info@example.ch"


def test_person_without_address_is_kept_and_still_a_failure():
    result = scrape(ok(page("/team", "team", "<p>Anna Muster, Founder</p>")))
    assert [p.name for p in result.people] == ["Anna Muster"]
    assert result.contact is None
    assert result.failure == "no_address"


def test_exception_in_fetcher_becomes_unreachable():
    result = scrape(error=RuntimeError("boom"))
    assert result.failure == "unreachable"
    assert result.pages_fetched == ()


def test_target_role_changes_the_person_proposed():
    outcome = ok(page("/team", "team",
                      "<div><div>Anna Muster</div><div>Co-Founder &amp; CEO</div></div>"
                      "<div><div>Clara Vorlage</div><div>Head of Product</div></div>"
                      "<p>info@example.ch</p>"))
    fetcher = FakeFetcher(outcome)
    assert scrape_company(COMPANY, fetcher).contact.person_name == "Anna Muster"
    proposed = scrape_company(COMPANY, fetcher, target_role="product").contact
    assert (proposed.person_name, proposed.address, proposed.confidence) == (
        "Clara Vorlage", "info@example.ch", "medium")


def test_address_without_anybody_kept_is_still_proposed():
    result = scrape(ok(page("/", "home", "<p>info@example.ch</p>")))
    assert result.people == ()
    assert (result.contact.address, result.contact.person_name, result.contact.confidence) == (
        "info@example.ch", None, "low")


def test_company_with_only_a_kept_persons_address_keeps_a_contact():
    result = scrape(ok(page("/team", "team",
                            "<div><div>Lena Beispiel</div><div>Head of Marketing</div></div>"
                            "<p>lena@example.ch</p>")))
    assert result.failure is None
    assert (result.contact.address, result.contact.person_name) == (
        "lena@example.ch", "Lena Beispiel")


def test_a_profile_page_on_another_organisation_s_site_is_not_read():
    class Unused:
        def fetch_site(self, website):
            raise AssertionError("must not be fetched")

    company = dict(COMPANY, name="Qubit Robotics",
                   website="https://www.example.com/qubit-robotics-systems")
    result = scrape_company(company, Unused())
    assert result.failure == "not_own_site"
    assert result.contact is None and result.people == () and result.pages_fetched == ()
