"""One company, from its website to a result with a contact or a failure cause."""

from bs4 import BeautifulSoup

from kaltstart.contacts.emails import extract_addresses
from kaltstart.contacts.founders import extract_founders
from kaltstart.contacts.models import (
    CompanyResult, FetchOutcome, FoundEmail, FoundFounder)
from kaltstart.contacts.selection import address_type, choose_contact
from kaltstart.contacts.site import site_host, visible_text

FAILURES = ("robots_forbidden", "unreachable", "little_text", "other_domain_only",
            "contact_form_only", "no_address")
LITTLE_TEXT_CHARS = 200


def _has_contact_form(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return any(form.find("textarea") for form in soup.find_all("form"))


def scrape_company(company: dict, fetcher) -> CompanyResult:
    """Scrape one company. Never raises: any error becomes its outcome."""
    try:
        outcome = fetcher.fetch_site(company["website"])
    except Exception:
        outcome = FetchOutcome("unreachable", (), (site_host(company["website"]),))

    addresses: dict[str, str] = {}      # address -> first source page
    founders: dict[str, FoundFounder] = {}
    other_domain = 0
    for page in outcome.pages:
        kept, others = extract_addresses(page, outcome.hosts)
        other_domain += others
        for address in kept:
            addresses.setdefault(address, page.url)
        for founder in extract_founders(page):
            founders.setdefault(founder.name, founder)

    founder_list = tuple(founders.values())
    emails = tuple(FoundEmail(address, address_type(address, founder_list), source)
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
        emails=emails, founders=founder_list,
        contact=choose_contact(emails, founder_list, company["size_category"]),
        failure=failure)
