# Phase 2: Contact Scraper Measurement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the contact scraper and measure, on 20 Swiss companies, how often it finds a usable address and a founder's name.

**Architecture:** A new package `kaltstart.contacts`, independent of the database. A fetcher downloads up to 8 pages of one site politely; pure functions choose pages, extract addresses and founder names, and choose the contact; `scrape_company` chains them and names a failure cause. Two commands feed and run it: `sample` (in the ingestion CLI, which has database access) draws the companies, `measure` and `summary` (in the contacts CLI) run the scraper on a CSV and compute the rates.

**Tech Stack:** Python 3.12+, httpx, beautifulsoup4 (HTML parsing), `urllib.robotparser` (standard library), pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-phase-2-contact-measurement-design.md`. Parent spec: `docs/superpowers/specs/2026-11-11-kaltstart-design.md` (sections 2, 7.2, 8, 9).

## Global Constraints

- No call to any AI API at runtime.
- No test makes a real network call. The fetcher is tested with `httpx.MockTransport` and an injected `sleep`.
- Never fetch LinkedIn or any host other than the company's own site. Never guess an address.
- `robots.txt` is read before any other request to a site and obeyed (`User-agent: *` rules).
- At least 2 seconds between two requests to the same site; at most 8 pages per company; 15-second timeout; 2 MB per page; HTML only.
- The `User-Agent` header is the HTTP library's default: no project name, no link, no browser imitation.
- Test fixtures are invented pages with invented people on `example.ch`, `example.de`, `example.com`. No real page, name or address is committed.
- Detailed results are written under `local/`, which is git-ignored. The repository receives only the sample and a summary without any name or address.
- Every file in the repository is in English. Commit messages use `type: description` and carry only the repository owner's identity, with no co-author trailer.
- Test-driven development: the test is written and seen failing before the code.
- Use the project's virtual environment: `.venv/bin/python`, `.venv/bin/pytest`.

## Review Focus

1. The website redirects to another domain (`startup.ch` to `startup.com`, or to `www.`): the home page's final host is accepted as the company's site, for links and for addresses. Test in Task 3.
2. A link on the home page is relative, a fragment, `mailto:`, `tel:`, `javascript:`, a file (`.pdf`, `.jpg`) or points to another site: only same-site HTML pages are followed, and the home page itself is never chosen again. Test in Task 2.
3. A response is not HTML, is larger than 2 MB, is badly encoded, or `robots.txt` answers with an error or a web page: the page is skipped, or `robots.txt` counts as "no restriction", and nothing crashes. Test in Task 3.
4. The same address appears on several pages or in different letter case: it is kept once, in lower case, with the first page as its source. Test in Task 7.
5. The website value has a path, upper-case letters, a trailing slash or no `www`: the site host is derived correctly, and an address on a parent domain of the host (`app.startup.ch` and `info@startup.ch`) counts as the company's domain. Test in Task 1.

---

## File structure

| File | Responsibility |
|---|---|
| `src/kaltstart/contacts/models.py` | Dataclasses exchanged between modules |
| `src/kaltstart/contacts/site.py` | Host and domain rules; visible text and links of an HTML page |
| `src/kaltstart/contacts/pages.py` | Which links of the home page to follow |
| `src/kaltstart/contacts/fetcher.py` | Polite download of one site |
| `src/kaltstart/contacts/emails.py` | Addresses in a page |
| `src/kaltstart/contacts/founders.py` | Founder names in a page |
| `src/kaltstart/contacts/selection.py` | Address type, proposed contact, confidence |
| `src/kaltstart/contacts/scrape.py` | One company from website to result, with its failure cause |
| `src/kaltstart/contacts/measurement.py` | Results CSV, rates, verdict, summary text |
| `src/kaltstart/contacts/__main__.py` | Commands `measure` and `summary` |
| `src/kaltstart/ingestion/__main__.py` | New command `sample` |
| `tests/contacts/` | One test file per module |
| `tests/fixtures/sites/` | Invented HTML pages |

Types, defined in `models.py` (Task 1) and used by every later task:

```python
@dataclass(frozen=True)
class Page:
    url: str
    kind: str            # "home" | "legal" | "contact" | "team" | "careers"
    html: str

@dataclass(frozen=True)
class FetchOutcome:
    status: str          # "ok" | "robots_forbidden" | "unreachable"
    pages: tuple[Page, ...]
    hosts: tuple[str, ...]   # accepted site hosts: the sample's, and the home page's final host

@dataclass(frozen=True)
class FoundEmail:
    address: str         # lower case
    type: str            # "personal" | "careers" | "generic"
    source_url: str

@dataclass(frozen=True)
class FoundFounder:
    name: str
    role: str
    source_url: str

@dataclass(frozen=True)
class ProposedContact:
    address: str
    founder_name: str | None
    confidence: str      # "high" | "medium" | "low"

@dataclass(frozen=True)
class CompanyResult:
    company_id: str
    name: str
    website: str
    size_category: str   # "small" | "medium" | "large"
    pages_fetched: tuple[str, ...]
    emails: tuple[FoundEmail, ...]
    founders: tuple[FoundFounder, ...]
    contact: ProposedContact | None
    failure: str | None  # None, or one of the six causes of spec 5.6
```

---

### Task 1: package skeleton, models, site rules, documents

**Files:**
- Create: `src/kaltstart/contacts/__init__.py`, `models.py`, `site.py`, `tests/contacts/__init__.py`, `tests/contacts/test_site.py`
- Modify: `pyproject.toml` (add `beautifulsoup4>=4.12,<5`), `.gitignore` (append `local/`), `CLAUDE.md`, `DECISIONS.md`, `docs/superpowers/specs/2026-11-11-kaltstart-design.md`

**Interfaces:**
- Produces: the dataclasses above, and in `site.py`:
  - `site_host(website: str) -> str`: lower-case host without a leading `www.`; accepts a value without a scheme.
  - `same_site(url: str, hosts: Iterable[str]) -> bool`: the URL's host, without `www.`, equals one of `hosts` or is a subdomain of one.
  - `on_company_domain(email_domain: str, hosts: Iterable[str]) -> bool`: the domain equals a host, is a subdomain of a host, or is a parent of a host and has at least two labels.
  - `visible_text(html: str) -> str`: text without `script`, `style`, `noscript` content, whitespace collapsed.
  - `links(html: str, base_url: str) -> list[tuple[str, str]]`: `(absolute_url, link_text)` for every `<a href>`, in document order, fragments removed.

- [ ] **Step 1:** write `tests/contacts/test_site.py`

```python
import pytest
from kaltstart.contacts.site import (
    links, on_company_domain, same_site, site_host, visible_text)

@pytest.mark.parametrize("website,expected", [
    ("https://www.Example.ch/", "example.ch"),
    ("https://example.ch/en/home", "example.ch"),
    ("app.example.ch", "app.example.ch"),
    ("HTTP://EXAMPLE.DE", "example.de"),
])
def test_site_host(website, expected):
    assert site_host(website) == expected

@pytest.mark.parametrize("url,expected", [
    ("https://example.ch/team", True),
    ("https://www.example.ch/team", True),
    ("https://jobs.example.ch/", True),
    ("https://example.com/team", False),
    ("https://notexample.ch/", False),
    ("https://www.linkedin.com/company/example", False),
])
def test_same_site(url, expected):
    assert same_site(url, ["example.ch"]) is expected

@pytest.mark.parametrize("domain,hosts,expected", [
    ("example.ch", ["example.ch"], True),
    ("mail.example.ch", ["example.ch"], True),
    ("example.ch", ["app.example.ch"], True),     # parent of the site host
    ("ch", ["app.example.ch"], False),            # a bare suffix is never a company domain
    ("example.com", ["example.ch", "example.com"], True),
    ("gmail.com", ["example.ch"], False),
])
def test_on_company_domain(domain, hosts, expected):
    assert on_company_domain(domain, hosts) is expected

def test_visible_text_drops_scripts_and_collapses_whitespace():
    html = "<html><head><style>p{}</style></head><body><script>var a=1</script><p>Hello\n  world</p></body></html>"
    assert visible_text(html) == "Hello world"

def test_links_are_absolute_in_order_without_fragments():
    html = '<a href="/team#top">Team</a><a href="https://example.com/x">X</a><a>no href</a>'
    assert links(html, "https://example.ch/") == [
        ("https://example.ch/team", "Team"), ("https://example.com/x", "X")]
```

- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_site.py -q`. Expected: failure at import.
- [ ] **Step 3:** add the dependency and run `.venv/bin/pip install -e ".[dev]"`; create the package, `models.py` with the dataclasses above, and `site.py`. Parse HTML with `BeautifulSoup(html, "html.parser")`.
- [ ] **Step 4:** run the test file again. Expected: all pass. Run `.venv/bin/pytest -q`. Expected: everything passes.
- [ ] **Step 5:** update the documents:
  - `.gitignore`: append `local/`.
  - `DECISIONS.md`: add D23 to D30, the eight rows of section 8 of the spec, in that order.
  - Parent spec, section 7.2: replace "a tool name that identifies the project" with "no project name in the `User-Agent` header (decision D27)"; replace the "Pages visited" bullet with "Pages visited: the home page, then links found on it for the legal notice, contact, team and about, and careers pages, with fixed paths as a fallback. Eight pages at most per company."
  - `CLAUDE.md`: add the constraints of this plan that are new (fixtures are invented pages; detailed results stay under `local/`; `User-Agent` rule), and mark `contacts/` as in progress.
- [ ] **Step 6:** commit `feat: add contacts package skeleton and site rules`.

### Task 2: choosing the pages

**Files:**
- Create: `src/kaltstart/contacts/pages.py`
- Test: `tests/contacts/test_pages.py`

**Interfaces:**
- Consumes: `links`, `same_site`.
- Produces:
  - `KINDS = ("legal", "contact", "team", "careers")`, in priority order.
  - `KEYWORDS: dict[str, tuple[str, ...]]` with exactly: legal `("impressum", "imprint", "legal")`; contact `("contact", "kontakt")`; team `("team", "about", "ueber-uns", "über uns", "about-us", "company", "unternehmen")`; careers `("careers", "career", "jobs", "karriere", "join")`.
  - `FALLBACK_PATHS: tuple[tuple[str, str], ...]` = `(("/impressum", "legal"), ("/imprint", "legal"), ("/contact", "contact"), ("/team", "team"), ("/about", "team"), ("/careers", "careers"), ("/jobs", "careers"))`.
  - `choose_links(home_html: str, home_url: str, hosts: Iterable[str], max_links: int = 7, per_kind: int = 2) -> list[tuple[str, str]]` returns `(url, kind)`.

- [ ] **Step 1:** write the tests:
  - `test_priority_order_and_kinds`: a home page linking, in this document order, to `/jobs`, `/team`, `/kontakt`, `/impressum` returns them as legal, contact, team, careers.
  - `test_keyword_matches_link_text_or_url_case_insensitively`: `<a href="/p/42">Über uns</a>` is `team`; `<a href="/KARRIERE">Work</a>` is `careers`.
  - `test_at_most_two_per_kind_and_seven_in_total`: three contact links give two; a page with two links of each of the four kinds plus more returns 7.
  - `test_only_same_site_html_pages` (Review Focus 2): links with `mailto:`, `tel:`, `javascript:`, `https://www.linkedin.com/company/x`, `/team.pdf`, `/team.jpg`, and a link back to the home URL (with and without trailing slash) are never returned; a relative `team/` is resolved against the home URL.
  - `test_duplicate_urls_are_returned_once`.
  - `test_fallback_paths_when_no_link_matches`: a home page without any matching link returns the seven `FALLBACK_PATHS` resolved against the home URL, in that order.
- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_pages.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `choose_links`. A link's kind is the first kind, in priority order, one of whose keywords occurs in the lower-cased link text or URL path. File links are those whose path ends with an extension other than `.html`, `.htm`, `.php`, `.aspx` or none.
- [ ] **Step 4:** run again. Expected: all pass.
- [ ] **Step 5:** commit `feat: choose which pages of a site to read`.

### Task 3: polite fetcher

**Files:**
- Create: `src/kaltstart/contacts/fetcher.py`
- Test: `tests/contacts/test_fetcher.py`

**Interfaces:**
- Consumes: `choose_links`, `site_host`, `same_site`, `Page`, `FetchOutcome`.
- Produces: `class SiteFetcher(http: httpx.Client, min_interval_s: float = 2.0, max_pages: int = 8, max_bytes: int = 2_000_000, sleep: Callable[[float], None] = time.sleep)` with `fetch_site(website: str) -> FetchOutcome`. The 15-second timeout is set on the `httpx.Client` by its creator (`default_http_client() -> httpx.Client` in the same file: `timeout=15`, `follow_redirects=True`, no custom headers).

The tests build `SiteFetcher(httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True), sleep=recorder)`.

- [ ] **Step 1:** write the tests, one per behaviour:
  - `test_robots_txt_is_requested_first`: the first request is `https://example.ch/robots.txt`.
  - `test_robots_forbidding_home_page_fetches_nothing_else`: `User-agent: *\nDisallow: /` gives `status == "robots_forbidden"`, no page, and exactly 1 request.
  - `test_robots_disallowed_page_is_skipped`: `Disallow: /team` and a home page linking to `/team` and `/kontakt`: `/team` is never requested, `/kontakt` is.
  - `test_missing_or_broken_robots_means_no_restriction` (Review Focus 3): `robots.txt` answering 404, 500, or an HTML page: the home page is fetched.
  - `test_fetches_home_then_chosen_links_with_kinds`: pages come back as `Page` objects with kinds `home`, then those given by `choose_links`.
  - `test_waits_two_seconds_between_requests`: every request after the first is preceded by a `sleep` call of at most 2.0 seconds, and the sleeps are positive when the clock does not advance.
  - `test_never_more_than_eight_pages`.
  - `test_home_redirect_to_another_domain_is_accepted` (Review Focus 1): `https://example.ch/` redirects to `https://www.example.com/`; `hosts == ("example.ch", "example.com")`; a link to `https://example.com/team` is followed.
  - `test_page_redirecting_off_site_is_dropped`: `/kontakt` redirects to `https://other.example.de/`: it is not in `pages`.
  - `test_non_html_and_oversized_pages_are_skipped` (Review Focus 3): a response with `content-type: application/pdf`, and one with a 3 MB body, are not in `pages`, and the run continues.
  - `test_undecodable_bytes_do_not_crash`: a body with invalid UTF-8 is returned as text with replacement characters.
  - `test_unreachable_when_home_page_fails`: the home page answers 500, or raises `httpx.ConnectError`, or times out: `status == "unreachable"`, no page.
  - `test_failing_secondary_page_is_skipped`: `/team` answers 404: status is `ok`, the other pages are returned.
  - `test_default_user_agent`: the `User-Agent` header of every request starts with `python-httpx/`.
- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_fetcher.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `SiteFetcher`. Parse `robots.txt` with `urllib.robotparser.RobotFileParser().parse(lines)` and ask it with user agent `"*"`; a non-200 answer or a body whose content type is HTML counts as no rules. The home URL is `https://<site_host>/` unless the sample's website has a path, in which case the website is used as given. Wait with `time.monotonic` and the injected `sleep`, as `TechEuClient` does in `src/kaltstart/ingestion/techeu_client.py`.
- [ ] **Step 4:** run again. Expected: all pass, in well under a second.
- [ ] **Step 5:** commit `feat: add polite site fetcher`.

### Task 4: addresses

**Files:**
- Create: `src/kaltstart/contacts/emails.py`, `tests/fixtures/sites/contact_page.html`
- Test: `tests/contacts/test_emails.py`

**Interfaces:**
- Consumes: `Page`, `visible_text`, `links`, `on_company_domain`.
- Produces: `extract_addresses(page: Page, hosts: Iterable[str]) -> tuple[list[str], int]` returns the addresses on the company's domain, lower case, in order of first appearance, without duplicates, and the number of distinct addresses found on other domains.

- [ ] **Step 1:** write the tests

```python
import pytest
from kaltstart.contacts.emails import extract_addresses
from kaltstart.contacts.models import Page

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
    "<p>We meet at example dot ch every week</p>",   # bare words inside a sentence
    "<p>See you at example.ch tomorrow</p>",
    "<script>var m='hidden@example.ch'</script>",
])
def test_noise_is_discarded(body):
    assert extract_addresses(page(body), ["example.ch"]) == ([], 0)
```

- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_emails.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `extract_addresses`. Sources: `mailto:` links (query string removed) and the visible text. The bracketed forms (`[at]`, `(at)`, `[dot]`, `(dot)`) are normalised anywhere in the text. The bare-word forms (` at `, ` dot `) are accepted only when the address is the whole text of its element, so that an ordinary sentence containing "at" never produces an address. Discard addresses whose domain is, or is a subdomain of, one of `TOOLING_DOMAINS = ("sentry.io", "wixpress.com")`, or whose domain ends with an image extension (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`); discarded addresses are not counted as other-domain.
- [ ] **Step 4:** run again. Expected: all pass. Also create `tests/fixtures/sites/contact_page.html`, an invented contact page with one `mailto:` address, one disguised address, a contact form with a `<textarea>`, and a LinkedIn link; add one test that it yields exactly the two addresses.
- [ ] **Step 5:** commit `feat: extract published addresses from a page`.

### Task 5: founder names

**Files:**
- Create: `src/kaltstart/contacts/founders.py`, `tests/fixtures/sites/impressum_de.html`, `tests/fixtures/sites/team_cards.html`
- Test: `tests/contacts/test_founders.py`

**Interfaces:**
- Consumes: `Page`, `FoundFounder`.
- Produces:
  - `ROLE_WORDS: tuple[str, ...]` = `("Co-Founder", "Cofounder", "Founder", "Chief Executive Officer", "CEO", "Managing Director", "Mitgründerin", "Mitgründer", "Gründerin", "Gründer", "Geschäftsführerin", "Geschäftsführer", "Geschäftsleitung")`, longest first so that `Co-Founder` wins over `Founder`.
  - `extract_founders(page: Page) -> list[FoundFounder]`: empty for pages whose kind is not `legal` or `team`; otherwise one entry per distinct name, in order of appearance.

- [ ] **Step 1:** write the tests

```python
import pytest
from kaltstart.contacts.founders import extract_founders
from kaltstart.contacts.models import Page

def names(body, kind="team"):
    page = Page("https://example.ch/team", kind, f"<html><body>{body}</body></html>")
    return [(f.name, f.role) for f in extract_founders(page)]

@pytest.mark.parametrize("body,expected", [
    ("<p>Geschäftsführer: Anna Muster</p>", [("Anna Muster", "Geschäftsführer")]),
    ("<p>Geschäftsführung / Geschäftsführer: Dr. Anna Muster, Jonas Beispiel</p>",
     [("Anna Muster", "Geschäftsführer"), ("Jonas Beispiel", "Geschäftsführer")]),
    ("<div><h3>Anna Muster</h3><p>Co-Founder &amp; CEO</p></div>", [("Anna Muster", "Co-Founder")]),
    ("<div><p>CEO</p><h3>Jonas von Beispiel</h3></div>", [("Jonas von Beispiel", "CEO")]),
    ("<p>Anna Muster, Founder</p>", [("Anna Muster", "Founder")]),
    ("<p>Gründerin Anna Maria Muster</p>", [("Anna Maria Muster", "Gründerin")]),
])
def test_names_next_to_a_role(body, expected):
    assert names(body) == expected

@pytest.mark.parametrize("body", [
    "<p>Founder of the Year Award</p>",
    "<p>Geschäftsführer: Example Ventures AG</p>",
    "<p>CEO Office 2nd Floor</p>",
    "<p>Our founders met in Zurich</p>",
    "<p>Backed by Founder Collective</p>",
])
def test_rejections(body):
    assert names(body) == []

def test_only_legal_and_team_pages_are_read():
    assert names("<p>Anna Muster, Founder</p>", kind="careers") == []
    assert names("<p>Anna Muster, Founder</p>", kind="legal") == [("Anna Muster", "Founder")]

def test_same_person_is_returned_once():
    assert names("<p>Anna Muster, Founder</p><p>CEO: Anna Muster</p>") == [("Anna Muster", "Founder")]
```

- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_founders.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `extract_founders`. Work block by block (each `p`, `li`, `td`, `div` without block children, and each heading with its next sibling block as one unit). In a unit containing a role word (whole word, case-insensitive for the English ones), a name is a run of two to four words each starting with an upper-case letter, with the lower-case particles `von`, `van`, `de`, `del`, `di` allowed inside; titles (`Dr.`, `Prof.`, `Dipl.-Ing.`) are dropped. Reject a candidate that contains a role word, a company suffix (`AG`, `GmbH`, `SA`, `Sàrl`, `Ltd`, `Inc`), a digit, or one of `("Award", "Collective", "Office", "Year", "Team")`.
- [ ] **Step 4:** run again. Expected: all pass. Create the two invented fixtures (a German legal notice with two managing directors and an address block; a team page with five cards, two of them founders, three employees) and add one test per fixture asserting the exact names returned.
- [ ] **Step 5:** commit `feat: extract founder names from legal and team pages`.

### Task 6: address type, contact and confidence

**Files:**
- Create: `src/kaltstart/contacts/selection.py`
- Test: `tests/contacts/test_selection.py`

**Interfaces:**
- Consumes: `FoundEmail`, `FoundFounder`, `ProposedContact`.
- Produces:
  - `CAREERS_LOCAL_PARTS = ("careers", "career", "jobs", "talent", "hr", "karriere", "recruiting")`.
  - `address_type(address: str, founders: Sequence[FoundFounder]) -> str`.
  - `choose_contact(emails: Sequence[FoundEmail], founders: Sequence[FoundFounder], size_category: str) -> ProposedContact | None`.

- [ ] **Step 1:** write the tests

```python
import pytest
from kaltstart.contacts.models import FoundEmail, FoundFounder, ProposedContact
from kaltstart.contacts.selection import address_type, choose_contact

ANNA = FoundFounder("Anna Muster", "Founder", "https://example.ch/team")

@pytest.mark.parametrize("address,founders,expected", [
    ("anna@example.ch", [ANNA], "personal"),
    ("a.muster@example.ch", [ANNA], "personal"),
    ("anna.muster@example.ch", [], "generic"),     # no founder found: never guessed as personal
    ("jobs@example.ch", [ANNA], "careers"),
    ("karriere@example.ch", [], "careers"),
    ("hello@example.ch", [ANNA], "generic"),
    ("info@example.ch", [], "generic"),
])
def test_address_type(address, founders, expected):
    assert address_type(address, founders) == expected

def mail(address, type_):
    return FoundEmail(address, type_, "https://example.ch/kontakt")

PERSONAL, CAREERS, GENERIC = (mail("anna@example.ch", "personal"),
                              mail("jobs@example.ch", "careers"),
                              mail("info@example.ch", "generic"))

@pytest.mark.parametrize("emails,founders,size,expected", [
    ([GENERIC, CAREERS, PERSONAL], [ANNA], "small", ProposedContact("anna@example.ch", "Anna Muster", "high")),
    ([GENERIC, CAREERS], [ANNA], "small", ProposedContact("info@example.ch", "Anna Muster", "medium")),
    ([CAREERS], [ANNA], "small", ProposedContact("jobs@example.ch", "Anna Muster", "medium")),
    ([GENERIC], [], "small", ProposedContact("info@example.ch", None, "low")),
    ([GENERIC, CAREERS], [], "small", ProposedContact("info@example.ch", None, "low")),
    ([CAREERS], [], "small", ProposedContact("jobs@example.ch", None, "medium")),
    ([GENERIC, CAREERS, PERSONAL], [ANNA], "medium", ProposedContact("jobs@example.ch", None, "medium")),
    ([GENERIC, PERSONAL], [ANNA], "large", ProposedContact("info@example.ch", None, "low")),
    ([PERSONAL], [ANNA], "large", None),
    ([], [ANNA], "small", None),
])
def test_choose_contact(emails, founders, size, expected):
    assert choose_contact(emails, founders, size) == expected
```

- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_selection.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement both functions. An address is personal when a founder was found and its local part, split on `.`, `-`, `_`, contains that founder's first name or last name in lower case, or equals the initial of the first name followed by the last name. For a small company without a personal address, the generic address is proposed before the careers one, with or without a founder's name: at a small company the general inbox is the one founders read. The confidence follows the parent spec's table: high for a personal address; medium for a careers address, or a generic one with a founder's name; low for a generic address alone.
- [ ] **Step 4:** run again. Expected: all pass.
- [ ] **Step 5:** commit `feat: classify addresses and choose the contact to propose`.

### Task 7: one company from website to result

**Files:**
- Create: `src/kaltstart/contacts/scrape.py`
- Test: `tests/contacts/test_scrape.py`

**Interfaces:**
- Consumes: `SiteFetcher.fetch_site`, `extract_addresses`, `extract_founders`, `address_type`, `choose_contact`, `visible_text`, the dataclasses.
- Produces:
  - `FAILURES = ("robots_forbidden", "unreachable", "little_text", "other_domain_only", "contact_form_only", "no_address")`.
  - `LITTLE_TEXT_CHARS = 200`.
  - `scrape_company(company: dict, fetcher) -> CompanyResult`, where `company` has the keys `company_id`, `name`, `website`, `size_category`, and `fetcher` is any object with `fetch_site(website) -> FetchOutcome`.

The tests use a fake fetcher returning a prepared `FetchOutcome`.

- [ ] **Step 1:** write the tests:
  - `test_result_with_contact`: a home page and a team page with a founder and a personal address: `failure is None`, `contact.confidence == "high"`, `pages_fetched` lists both URLs, each email carries its type and source URL.
  - `test_address_seen_on_two_pages_is_kept_once` (Review Focus 4): `Info@example.ch` on the home page and `info@example.ch` on the contact page give one `FoundEmail` in lower case, with the home page as its source.
  - `test_failure_causes`, parametrized: outcome status `robots_forbidden` gives that cause; status `unreachable` gives that cause; pages whose visible text totals fewer than 200 characters give `little_text`; pages with only an address on another domain give `other_domain_only`; pages with no address and a `<form>` containing a `<textarea>` give `contact_form_only`; pages with text and nothing else give `no_address`.
  - `test_cause_priority`: little text and a form together give `little_text`; an other-domain address and a form together give `other_domain_only`.
  - `test_founder_without_address_is_kept_and_still_a_failure`: a founder name and no address: `founders` is filled, `contact is None`, `failure == "no_address"`.
  - `test_exception_in_fetcher_becomes_unreachable`: a fetcher raising `RuntimeError` gives a result with `failure == "unreachable"`, and no exception escapes.
- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_scrape.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `scrape_company`. Addresses are typed with `address_type` after all founders of all pages are known. `failure` is `None` exactly when at least one address on the company's domain was kept.
- [ ] **Step 4:** run again. Expected: all pass.
- [ ] **Step 5:** commit `feat: scrape one company and name its failure cause`.

### Task 8: drawing the sample

**Files:**
- Modify: `src/kaltstart/ingestion/__main__.py`, `.github/workflows/nightly.yml`
- Test: `tests/ingestion/test_cli.py`

**Interfaces:**
- Consumes: `store.all_rounds_with_company()`.
- Produces: command `sample [--country Switzerland] [--n 20] [--seed 2026] [--exclude-seed SEED ...]`, printing CSV to standard output with the header `company_id,name,website,size_category`.

- [ ] **Step 1:** write the tests, with an `InMemoryStore` holding 30 Swiss companies with a website, 5 Swiss companies without one, and 10 German companies:
  - `test_sample_prints_20_swiss_companies_with_a_website`: 21 lines including the header; every row's website is non-empty; no German company.
  - `test_sample_is_reproducible`: two runs with the same seed print the same text; seed 2027 prints a different list.
  - `test_sample_size_category_is_that_of_the_latest_round`: a company with a `small` round in 2026-01 and a `large` round in 2026-06 is listed as `large`.
  - `test_sample_exclude_seed`: `--seed 2027 --exclude-seed 2026` shares no company with the seed-2026 list.
  - `test_sample_with_fewer_companies_than_n_prints_them_all`.
  - `test_sample_never_builds_a_client`.
- [ ] **Step 2:** run `.venv/bin/pytest tests/ingestion/test_cli.py -q`. Expected: the new tests fail.
- [ ] **Step 3:** implement the command. Candidates are sorted by `company_id` before `random.Random(seed).sample(...)`, so the draw does not depend on the order the database returns rows. Write with the `csv` module.
- [ ] **Step 4:** run `.venv/bin/pytest -q`. Expected: everything passes.
- [ ] **Step 5:** in `.github/workflows/nightly.yml`, add `sample` to the `command` options and a second manual input `args` (type `string`, default empty, description "Extra arguments for the command"). Pass it through an environment variable, like the command: `ARGS: ${{ github.event.inputs.args }}` and `run: python -m kaltstart.ingestion "$COMMAND" $ARGS` (unquoted on purpose, so the shell splits it into words; no `${{ }}` expression inside `run:`). Check the file still parses as YAML.
- [ ] **Step 6:** commit `feat: add sample command to draw companies for the measurement`.

### Task 9: measure and summary commands

**Files:**
- Create: `src/kaltstart/contacts/measurement.py`, `src/kaltstart/contacts/__main__.py`
- Test: `tests/contacts/test_measurement.py`, `tests/contacts/test_cli.py`

**Interfaces:**
- Consumes: `scrape_company`, `SiteFetcher`, `default_http_client`, `CompanyResult`.
- Produces, in `measurement.py`:
  - `RESULT_COLUMNS = ("company_id", "name", "website", "size_category", "pages_fetched", "emails", "founders", "contact_address", "contact_founder", "confidence", "failure", "email_check", "founder_check", "notes")`. `emails` holds `address|type|source_url` entries joined by ` ; `, `founders` holds `name|role|source_url` the same way, `pages_fetched` is a count. The last three columns are written empty.
  - `CHECK_VALUES = ("confirmed", "wrong", "missed", "none_exists")`: confirmed, the scraper's find is right; wrong, the scraper reported something false; missed, the site publishes one and the scraper found none; none_exists, nothing to find and nothing reported.
  - `write_results(results: Sequence[CompanyResult], path: Path) -> None`, `read_results(path: Path) -> list[dict]`.
  - `verdict(count: int, n: int, threshold: float) -> str`: `"inconclusive"` when `abs(count - threshold * n) <= 1`, else `"pass"` or `"fail"`.
  - `summarise(rows: Sequence[dict]) -> str`: the Markdown text of spec section 6. It contains no company name, no website, no address and no person's name.
- Produces, in `__main__.py`: `main(argv: list[str], *, fetcher=None) -> int` with
  - `measure SAMPLE_CSV [--out local/phase-2-results.csv]`: scrapes each row, writes the results file, prints the reported rates. Exit 0.
  - `summary RESULTS_CSV [--out docs/measurements/phase-2-summary.md]`: fails with exit 1 and a message naming the rows if any `email_check` or `founder_check` is empty or not in `CHECK_VALUES`; otherwise writes the summary. Exit 0.

- [ ] **Step 1:** write `tests/contacts/test_measurement.py`:
  - `test_write_then_read_round_trip`: the columns are exactly `RESULT_COLUMNS`; the three verification columns are empty.
  - `test_verdict`, parametrized with `n=20`: for threshold 0.7, counts 12, 13, 14, 15, 16 give fail, inconclusive, inconclusive, inconclusive, pass; for threshold 0.4, counts 6, 7, 8, 9, 10 give fail, inconclusive, inconclusive, inconclusive, pass.
  - `test_summarise_rates_and_mistakes`: 20 rows built in the test, of which 16 have an address reported (15 confirmed, 1 wrong), 2 missed and 2 none_exists; 9 founders reported (8 confirmed, 1 wrong), 3 missed: the text contains `Usable contact: reported 16/20 (80%), confirmed 15/20 (75%)`, `Founder name: reported 9/20 (45%), confirmed 8/20 (40%)`, `wrong address: 1`, `missed address: 2`, `wrong founder name: 1`, `missed founder name: 3`, one line per failure cause with its count, a table of confidence by size category, and the two verdicts.
  - `test_summarise_contains_no_personal_data`: none of the names, websites, addresses or company names of the rows appears in the text.
- [ ] **Step 2:** write `tests/contacts/test_cli.py` with a fake fetcher:
  - `test_measure_writes_results_and_prints_reported_rates` (uses `tmp_path`).
  - `test_measure_continues_after_a_failing_company`.
  - `test_summary_refuses_unverified_results`: exit 1, the message names the `company_id` values with an empty check.
  - `test_summary_writes_file`: exit 0, the file starts with `# Phase 2 measurement`.
  - `test_no_command_returns_2`.
- [ ] **Step 3:** run `.venv/bin/pytest tests/contacts -q`. Expected: the new files fail at import.
- [ ] **Step 4:** implement `measurement.py` and `__main__.py`. Without an injected `fetcher`, `measure` builds `SiteFetcher(default_http_client())`. `measure` creates the output directory if needed and prints one progress line per company (`3/20 example.ch: ok` or the failure cause).
- [ ] **Step 5:** run `.venv/bin/pytest -q -W error`. Expected: everything passes.
- [ ] **Step 6:** commit `feat: add measure and summary commands`.

### Task 10: the measurement

Steps marked **[Owner]** need the project owner.

- [ ] **Step 1:** push the branch's code to `main` once the whole-branch review is done (the `sample` command must be on `main` for the workflow).
- [ ] **Step 2:** run `gh workflow run nightly -f command=sample`, copy the CSV from the log into `docs/measurements/phase-2-sample.csv`, check it has 20 rows, commit `docs: add phase 2 sample`.
- [ ] **Step 3 [Owner]:** run `.venv/bin/python -m kaltstart.contacts measure docs/measurements/phase-2-sample.csv`. Expected: about 10 minutes, a file `local/phase-2-results.csv`, and `git status` showing nothing new.
- [ ] **Step 4:** first verification pass: visit each of the 20 sites, fill `email_check`, `founder_check` and `notes` in `local/phase-2-results.csv`. Use the cheapest model and page text, not screenshots.
- [ ] **Step 5 [Owner]:** open the source links of the reported finds, and check 5 companies independently, drawn with `random.Random(2026).sample(range(20), 5)`. If any of the 5 disagrees with the first pass, all 20 are checked again.
- [ ] **Step 6:** run `.venv/bin/python -m kaltstart.contacts summary local/phase-2-results.csv`, read the two verdicts.
- [ ] **Step 7:** if a verdict is `inconclusive`, draw 20 more with `gh workflow run nightly -f command=sample -f args="--seed 2027 --exclude-seed 2026"`, append them to the sample file, and repeat Steps 3 to 6 so that the summary covers the 40 companies.
- [ ] **Step 8:** record the result in `DECISIONS.md` (rates reported and confirmed, verdicts, the most frequent failure causes), update `README.md` (Phase 2 status and the summary's figures) and `CHANGELOG.md`. Commit `docs: record phase 2 measurement`.
- [ ] **Step 9 [Owner]:** decide the next step with the verdicts in hand: the second plan (nightly run and `contacts` table) if both pass, or a plan B from the parent spec, section 2.
