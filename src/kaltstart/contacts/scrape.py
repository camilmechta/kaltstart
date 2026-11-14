"""One company, from its website to a result with a contact or a failure cause."""

from bs4 import BeautifulSoup

from kaltstart.contacts.emails import extract_addresses
from kaltstart.contacts.models import (
    CompanyResult, FetchOutcome, FoundEmail, FoundPerson)
from kaltstart.contacts.people import extract_people
from kaltstart.contacts.selection import address_type, choose_contact, choose_person
from kaltstart.contacts.site import profile_on_another_site, site_host, visible_text

FAILURES = ("robots_forbidden", "unreachable", "little_text", "other_domain_only",
            "contact_form_only", "no_address", "not_own_site")
LITTLE_TEXT_CHARS = 200


def _has_contact_form(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return any(form.find("textarea") for form in soup.find_all("form"))


def scrape_company(company: dict, fetcher,
                   target_role: str | None = None) -> CompanyResult:
    """Scrape one company. Never raises: any error becomes its outcome.

    `target_role` is the role a student asks for; it decides who is proposed.
    """
    if profile_on_another_site(company["website"], company["name"]):
        return CompanyResult(
            company_id=company["company_id"], name=company["name"],
            website=company["website"], size_category=company["size_category"],
            pages_fetched=(), emails=(), people=(), contact=None, failure="not_own_site")
    try:
        outcome = fetcher.fetch_site(company["website"])
    except Exception:
        outcome = FetchOutcome("unreachable", (), (site_host(company["website"]),))

    addresses: dict[str, str] = {}      # address -> first source page
    people: dict[str, FoundPerson] = {}
    other_domain = 0
    for page in outcome.pages:
        kept, others = extract_addresses(page, outcome.hosts)
        other_domain += others
        for address in kept:
            addresses.setdefault(address, page.url)
        for person in extract_people(page, company["name"]):
            people.setdefault(person.name, person)

    people_list = tuple(people.values())
    emails = tuple(FoundEmail(address, address_type(address, people_list), source)
                   for address, source in addresses.items())

    failure = None
    if not emails:
        if outcome.status != "ok":
            failure = outcome.status
        elif sum(len(visible_text(p.html)) for p in outcome.pages) < LITTLE_TEXT_CHARS:
            failure = "little_text"
        elif other_domain:
            failure = "other_domain_only"
        elif any(_has_contact_form(p.html) for p in outcome.pages):
            failure = "contact_form_only"
        else:
            failure = "no_address"

    return CompanyResult(
        company_id=company["company_id"], name=company["name"],
        website=company["website"], size_category=company["size_category"],
        pages_fetched=tuple(p.url for p in outcome.pages),
        emails=emails, people=people_list,
        contact=choose_contact(emails, choose_person(
            people_list, target_role, company["size_category"]), people_list),
        failure=failure)
