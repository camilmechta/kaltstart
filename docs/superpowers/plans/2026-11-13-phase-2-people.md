# Phase 2: People Instead Of Founders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the contact scraper read the people a company presents with their job title, keep leaders, function heads, managers and recruiters, propose the right one for a student's target role, and measure it against two new criteria.

**Architecture:** A new pure module classifies a job title into categories and a level. `founders.py` becomes `people.py`: the page-layout reading it already does (card, line, label, testimonial and other-organisation rejection) is kept, and what marks a block is now a classified title instead of a founder word. Selection takes the student's target role. The measurement reports accuracy and coverage. Addresses are not touched.

**Tech Stack:** Python 3.12+, beautifulsoup4, pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-13-phase-2-people-design.md`. It amends `docs/superpowers/specs/2026-11-12-phase-2-contact-measurement-design.md` and `docs/superpowers/specs/2026-11-11-kaltstart-design.md`.

## Global Constraints

- No call to any AI API at runtime. No test makes a real network call.
- An address is never guessed or constructed. Nothing in `emails.py`, `fetcher.py`, `pages.py` or `site.py` changes in this plan.
- Running prose is never read for people: a title block has at most 14 words, a name block at most 8.
- A person tied to another organisation, or sitting with a quotation, is never returned (decisions D37 and D40 stay in force).
- Test fixtures are invented pages with invented people on `example.ch`, `example.de`, `example.com`. No real page, name or address is committed. Detailed results stay under `local/`.
- Every file in the repository is in English. Commit messages use `type: description` and carry only the repository owner's identity, with no co-author trailer.
- Test-driven development: the test is written and seen failing before the code.
- Use the project's virtual environment: `.venv/bin/python`, `.venv/bin/pytest`.
- Thresholds: usable contact 65 %, people accuracy 90 % (blocking), people coverage 40 % (a goal).

## Review Focus

1. A title that names two functions or a function and a leadership role ("Co-Founder & Head of Product", "Product Marketing Manager"): the person carries every category, and is proposed to a student targeting either. Test in Tasks 1 and 3.
2. A title that looks like a kept one but is not ("Account Manager", "Project Manager", "Office Manager", "Product Owner", "Head of Engineering", "Founder Associate"): never classified. Test in Task 1.
3. A team page listing thirty people of whom three are heads: only the three are returned, in page order, each once even if the page repeats them (desktop and mobile copies). Test in Task 2.
4. A company whose only person kept has no address of their own, and a company with an address but nobody kept: a contact is still proposed in both cases, with the confidence the spec gives. Test in Task 3.
5. A results file written before this plan (columns `founders`, `founder_check`): `summary` refuses it with a message naming the missing column, instead of reporting empty rates. Test in Task 4.

---

## File structure

| File | Change |
|---|---|
| `src/kaltstart/contacts/titles.py` | New. Categories, levels, `classify_title` |
| `src/kaltstart/contacts/people.py` | New, from `founders.py`. `extract_people` |
| `src/kaltstart/contacts/founders.py` | Deleted |
| `src/kaltstart/contacts/models.py` | `FoundPerson` replaces `FoundFounder`; `ProposedContact.person_name`; `CompanyResult.people` |
| `src/kaltstart/contacts/selection.py` | `choose_person`, new `choose_contact`, `address_type` over people |
| `src/kaltstart/contacts/scrape.py` | Uses `extract_people` and the new selection |
| `src/kaltstart/contacts/measurement.py` | Columns, accuracy, coverage, verdicts |
| `tests/contacts/test_titles.py`, `test_people.py` | New; `test_founders.py` is deleted after its cases are carried over |

Types (Task 2 defines them in `models.py`; every later task uses them):

```python
@dataclass(frozen=True)
class FoundPerson:
    name: str
    title: str                    # exactly as the site writes it, whitespace collapsed
    categories: tuple[str, ...]   # in the order of titles.CATEGORIES
    level: str                    # "head" | "manager"
    source_url: str

@dataclass(frozen=True)
class ProposedContact:
    address: str
    person_name: str | None
    confidence: str               # "high" | "medium" | "low"
```

`CompanyResult.founders` becomes `people: tuple[FoundPerson, ...]`.

---

### Task 1: job titles

**Files:**
- Create: `src/kaltstart/contacts/titles.py`
- Test: `tests/contacts/test_titles.py`

**Interfaces:**
- Produces:
  - `CATEGORIES = ("leadership", "product", "growth", "data", "operations", "sales", "recruiting")`
  - `ROLE_TO_CATEGORY = {"product": "product", "growth": "growth", "data": "data", "ops": "operations", "bd": "sales"}`
  - `@dataclass(frozen=True) class Title: categories: tuple[str, ...]; level: str`
  - `classify_title(text: str) -> Title | None`

- [ ] **Step 1:** write the tests

```python
import pytest
from kaltstart.contacts.titles import CATEGORIES, ROLE_TO_CATEGORY, Title, classify_title

@pytest.mark.parametrize("text,categories,level", [
    ("Co-Founder & CEO", ("leadership",), "head"),
    ("Founder - CEO/CTO", ("leadership",), "head"),
    ("Chief Executive Officer", ("leadership",), "head"),
    ("Managing Director", ("leadership",), "head"),
    ("President & CEO", ("leadership",), "head"),
    ("CTO", ("leadership",), "head"),
    ("Chief Financial Officer", ("leadership",), "head"),
    ("Geschäftsführerin", ("leadership",), "head"),
    ("Mitgründer und CTO", ("leadership",), "head"),
    ("Directrice générale", ("leadership",), "head"),
    ("Cofondateur", ("leadership",), "head"),
    ("Head of Product", ("product",), "head"),
    ("VP Product", ("product",), "head"),
    ("Chief Product Officer", ("product",), "head"),
    ("Product Lead", ("product",), "head"),
    ("Product Manager", ("product",), "manager"),
    ("Senior Product Manager", ("product",), "manager"),
    ("Leiter Produktmanagement", ("product",), "head"),
    ("VP Marketing", ("growth",), "head"),
    ("CMO", ("growth",), "head"),
    ("Head of Growth", ("growth",), "head"),
    ("Marketing Manager", ("growth",), "manager"),
    ("Head of Data & Analytics", ("data",), "head"),
    ("Chief Data Officer", ("data",), "head"),
    ("Head of Operations", ("operations",), "head"),
    ("Responsable des opérations", ("operations",), "head"),
    ("Operations Manager", ("operations",), "manager"),
    ("Head of Business Development", ("sales",), "head"),
    ("Leiterin Vertrieb", ("sales",), "head"),
    ("Chief Revenue Officer", ("sales",), "head"),
    ("Sales Director", ("sales",), "head"),
    ("Chief People Officer", ("recruiting",), "head"),
    ("Head of People & Culture", ("recruiting",), "head"),
    ("Talent Acquisition Lead", ("recruiting",), "head"),
    ("HR Manager", ("recruiting",), "manager"),
    ("Responsable ressources humaines", ("recruiting",), "head"),
    # Several categories (Review Focus 1); the level is the highest one.
    ("Co-Founder & Head of Product", ("leadership", "product"), "head"),
    ("Product Marketing Manager", ("product", "growth"), "manager"),
    ("Board Member & Co-Founder", ("leadership",), "head"),
    ("Co-Founder, Advisor & ETH Professor", ("leadership",), "head"),
])
def test_titles_kept(text, categories, level):
    assert classify_title(text) == Title(categories, level)

@pytest.mark.parametrize("text", [
    # Review Focus 2: looks like a kept title, is not.
    "Account Manager", "Project Manager", "Office Manager", "Product Owner",
    "Customer Success Manager", "Head of Engineering", "Engineering Manager",
    "Founder Associate", "Head of CEO Office", "Founders Associate",
    # No head or manager title.
    "Software Engineer", "Product Designer", "Data Scientist", "Sales Representative",
    "Marketing Intern", "Working Student Marketing", "Werkstudent Vertrieb",
    # Not the company's own leaders.
    "Board Member", "Advisor", "Investor", "Chairman of the Board",
    # Not held, or held for someone else.
    "Former CEO", "Ex-CEO", "Assistant to the CEO", "Personal Assistant to the Founder & CEO",
    # Not a title at all.
    "", "Anna Muster", "Our team", "About us",
])
def test_titles_not_kept(text):
    assert classify_title(text) is None

def test_constants():
    assert CATEGORIES == ("leadership", "product", "growth", "data", "operations",
                          "sales", "recruiting")
    assert ROLE_TO_CATEGORY == {"product": "product", "growth": "growth", "data": "data",
                                "ops": "operations", "bd": "sales"}
```

- [ ] **Step 2:** run `.venv/bin/pytest tests/contacts/test_titles.py -q`. Expected: failure at import.
- [ ] **Step 3:** implement `titles.py`. Approach, so that the tests determine one implementation:
  - Reject first: the text matches `former`, `ex-`, `assistant`, `associate`, `office` right after a leadership word, `intern`, `working student`, `werkstudent`, `praktikant`.
  - `leadership` when a leadership word is present as a whole word: the role words of the current `founders.ROLE_WORDS`, plus `President`, `COO`, `CFO`, `CTO`, `Chief Operating Officer`, `Chief Financial Officer`, `Chief Technology Officer`, `Fondateur`, `Fondatrice`, `Cofondateur`, `Cofondatrice`, `Directeur général`, `Directrice générale`.
  - A function category needs BOTH a function word of the spec's table (4.2) and a level word in the same title; the chief-officer acronyms and spelled-out forms of the table count as both. Level words: `head` for `Head`, `Director`, `VP`, `Vice President`, `Chief`, `Lead`, `Leiter`, `Leiterin`, `Bereichsleiter`, `Bereichsleiterin`, `Directeur`, `Directrice`, `Responsable`; `manager` for `Manager`. German compounds count: `Produktmanagement`, `Vertriebsleiter`.
  - `Manager` qualifies only when the function word stands right before it, or with one function word between ("Product Marketing Manager"); this is what excludes "Account Manager" and "Project Manager".
  - Categories are returned in `CATEGORIES` order. The level is `head` if any matched category is at head level or `leadership` matched, else `manager`.
- [ ] **Step 4:** run again. Expected: all pass.
- [ ] **Step 5:** commit `feat: classify job titles into categories and levels`.

### Task 2: reading people

**Files:**
- Create: `src/kaltstart/contacts/people.py`, `tests/contacts/test_people.py`
- Delete: `src/kaltstart/contacts/founders.py`, `tests/contacts/test_founders.py`
- Modify: `src/kaltstart/contacts/models.py`, `tests/fixtures/sites/team_cards.html`

**Interfaces:**
- Consumes: `classify_title`, `Page`.
- Produces: `FoundPerson` (above), and `extract_people(page: Page, company_name: str | None = None) -> list[FoundPerson]`: empty for pages whose kind is not `home`, `legal` or `team`; otherwise one entry per distinct name, in page order.

- [ ] **Step 1:** move `tests/contacts/test_founders.py` to `tests/contacts/test_people.py` with `git mv`, and adapt it: the helper returns `[(p.name, p.title) for p in extract_people(page, company)]`, and each expected role word becomes the title as written in that test's HTML (for `card("Dr Jonas Beispiel", "Chief Technology Officer & Co-Founder")` the expectation is `("Jonas Beispiel", "Chief Technology Officer & Co-Founder")`). Every existing case stays, with the same people accepted and rejected. For a label line ("Geschäftsführer: Dr. Anna Muster, Jonas Beispiel") the title is the label's title words ("Geschäftsführer").
- [ ] **Step 2:** add the new cases to `test_people.py`:

```python
@pytest.mark.parametrize("body,expected", [
    (card("Jonas Beispiel", "Head of Product"), [("Jonas Beispiel", "Head of Product", ("product",), "head")]),
    (card("Clara Vorlage", "Product Manager"), [("Clara Vorlage", "Product Manager", ("product",), "manager")]),
    (card("Mia Probe", "Head of People &amp; Culture"),
     [("Mia Probe", "Head of People & Culture", ("recruiting",), "head")]),
    (card("Anna Muster", "Co-Founder &amp; Head of Product"),
     [("Anna Muster", "Co-Founder & Head of Product", ("leadership", "product"), "head")]),
    ("<p>Leo Entwurf, Head of Sales</p>", [("Leo Entwurf", "Head of Sales", ("sales",), "head")]),
    (card("Noah Entwurf", "President &amp; CEO"), [("Noah Entwurf", "President & CEO", ("leadership",), "head")]),
])
def test_people_with_function_titles(body, expected):
    page = Page("https://example.ch/team", "team", f"<html><body>{body}</body></html>")
    assert [(p.name, p.title, p.categories, p.level)
            for p in extract_people(page, COMPANY)] == expected

@pytest.mark.parametrize("body", [
    card("Mia Probe", "Software Engineer"),
    card("Mia Probe", "Head of Engineering"),
    card("Mia Probe", "Account Manager"),
    card("Mia Probe", "Board Member"),
    card("Mia Probe", "Head of Product, Other Works"),       # at another organisation
    card("Mia Probe", "Head of Product at Other Works"),
])
def test_people_not_kept(body):
    assert names(body) == []
```

  And two page-level tests:
  - `test_large_team_page_keeps_only_heads_and_managers` (Review Focus 3): rewrite `tests/fixtures/sites/team_cards.html` as an invented page of thirty cards (2 founders, 1 Head of Product, 1 Product Manager, 1 HR Manager, 25 individual contributors with titles such as Software Engineer, Designer, Working Student), followed by a hidden mobile copy of the first five cards. Expected: exactly the five kept people, in page order, each once.
  - `test_source_url_and_page_kinds`: `source_url` is the page URL; kinds `contact` and `careers` return nothing.
- [ ] **Step 3:** run `.venv/bin/pytest tests/contacts/test_people.py -q`. Expected: failure at import.
- [ ] **Step 4:** in `models.py`, replace `FoundFounder` with `FoundPerson`. Create `people.py` from `founders.py` with `git mv`, then change it:
  - A block is a title block when it has at most 14 words and `classify_title` accepts the title part of its text. The founder-word regular expression and `ROLE_WORDS` are removed; the reject-before and reject-after patterns move to `titles.py` (Task 1 already covers them).
  - The title part of a block: for a card, the whole block text; for a line "Name, title" or "Name - title", the text after the leading name and its separator; for a label "title: Name, Name", the label.
  - The other-organisation rule (`_held_here`) is applied to the title text as today: an organisation right after the title words, right before them, or alone after a comma rejects the person, unless it is this company.
  - Names, the neighbour search (two levels up, empty neighbours skipped), the testimonial rule and the skipped tags are unchanged.
  - `_VOCABULARY` stays as the list of words that are never part of a person's name.
- [ ] **Step 5:** run `.venv/bin/pytest tests/contacts/test_people.py -q`. Expected: all pass. The rest of the suite fails at import until Task 3; that is expected.
- [ ] **Step 6:** commit `feat: read people with their job title instead of founders`.

### Task 3: who is proposed

**Files:**
- Modify: `src/kaltstart/contacts/selection.py`, `src/kaltstart/contacts/scrape.py`, `src/kaltstart/contacts/models.py`
- Test: `tests/contacts/test_selection.py`, `tests/contacts/test_scrape.py`

**Interfaces:**
- Consumes: `FoundPerson`, `FoundEmail`, `ROLE_TO_CATEGORY`.
- Produces, in `selection.py`:
  - `address_type(address: str, people: Sequence[FoundPerson]) -> str`: `personal` when the local part carries the last name of a person kept or is exactly their first name (D35), else `careers`, else `generic`.
  - `choose_person(people: Sequence[FoundPerson], target_role: str | None, size_category: str) -> FoundPerson | None`
  - `choose_contact(emails: Sequence[FoundEmail], person: FoundPerson | None) -> ProposedContact | None`
- In `scrape.py`: `scrape_company(company, fetcher, target_role: str | None = None)`; `CompanyResult.people`; `contact` is `choose_contact(emails, choose_person(people, target_role, size))`.

- [ ] **Step 1:** rewrite `tests/contacts/test_selection.py`. Keep the `address_type` cases, with `FoundPerson` in place of the founder. Add:

```python
def person(name, title, categories, level="head"):
    return FoundPerson(name, title, categories, level, "https://example.ch/team")

FOUNDER = person("Anna Muster", "Co-Founder & CEO", ("leadership",))
CTO = person("Jonas Beispiel", "CTO", ("leadership",))
HEAD_PRODUCT = person("Clara Vorlage", "Head of Product", ("product",))
PM = person("Mia Probe", "Product Manager", ("product",), "manager")
HR = person("Noah Entwurf", "HR Manager", ("recruiting",), "manager")
HEAD_PEOPLE = person("Lea Stark", "Head of People", ("recruiting",))
FOUNDER_PRODUCT = person("Leo Probe", "Co-Founder & Head of Product", ("leadership", "product"))

@pytest.mark.parametrize("people,role,size,expected", [
    # 1. Someone in the category of the target role; head before manager; page order.
    ([FOUNDER, PM, HEAD_PRODUCT], "product", "small", HEAD_PRODUCT),
    ([FOUNDER, PM], "product", "large", PM),
    ([FOUNDER, FOUNDER_PRODUCT], "product", "small", FOUNDER_PRODUCT),
    # 2. Otherwise, small company: leadership; a founder before another leader.
    ([CTO, FOUNDER, HR], "growth", "small", FOUNDER),
    ([CTO, HR], "growth", "small", CTO),
    ([FOUNDER, HEAD_PRODUCT], None, "small", FOUNDER),
    # 3. Otherwise, medium or large: recruiting; head before manager.
    ([FOUNDER, HR, HEAD_PEOPLE], "data", "medium", HEAD_PEOPLE),
    ([FOUNDER, HR], "data", "large", HR),
    # 4. Otherwise nobody.
    ([FOUNDER], "data", "large", None),
    ([HR], "growth", "small", None),
    ([], "product", "small", None),
])
def test_choose_person(people, role, size, expected):
    assert choose_person(people, role, size) == expected

OWN = FoundEmail("clara.vorlage@example.ch", "personal", "https://example.ch/team")
OTHER_PERSONAL = FoundEmail("anna@example.ch", "personal", "https://example.ch/team")
CAREERS = FoundEmail("jobs@example.ch", "careers", "https://example.ch/jobs")
GENERIC = FoundEmail("info@example.ch", "generic", "https://example.ch/")

@pytest.mark.parametrize("emails,chosen,expected", [
    ([GENERIC, CAREERS, OWN], HEAD_PRODUCT, ProposedContact("clara.vorlage@example.ch", "Clara Vorlage", "high")),
    ([GENERIC, CAREERS, OTHER_PERSONAL], HEAD_PRODUCT, ProposedContact("jobs@example.ch", "Clara Vorlage", "medium")),
    ([GENERIC], HEAD_PRODUCT, ProposedContact("info@example.ch", "Clara Vorlage", "medium")),
    ([GENERIC, CAREERS], None, ProposedContact("jobs@example.ch", None, "medium")),
    ([GENERIC], None, ProposedContact("info@example.ch", None, "low")),
    ([OTHER_PERSONAL], HEAD_PRODUCT, None),     # somebody else's address is never proposed
    ([OTHER_PERSONAL], None, None),
    ([], HEAD_PRODUCT, None),
])
def test_choose_contact(emails, chosen, expected):
    assert choose_contact(emails, chosen) == expected
```

- [ ] **Step 2:** adapt `tests/contacts/test_scrape.py`: `result.people` in place of `result.founders`; `contact.person_name`; a founder is now a `FoundPerson` with title and categories. Add `test_target_role_changes_the_person_proposed`: a small company page with a founder and a Head of Product gives `contact.person_name` equal to the founder's name without a target role, and to the head of product's with `target_role="product"`. Keep every failure-cause test unchanged: a company with a person and no address still fails with `no_address` and `contact is None` (Review Focus 4, second half).
- [ ] **Step 3:** run `.venv/bin/pytest tests/contacts/test_selection.py tests/contacts/test_scrape.py -q`. Expected: failures.
- [ ] **Step 4:** implement. `choose_person` follows the table of spec section 5; a founder is a person whose title matches a founder word (`founder`, `gründer`, `fondateur`, `fondatrice`, with their co- and mit- forms). `choose_contact` order: the chosen person's own address (the `personal` address whose local part matches that person), else careers, else generic, else none. Confidence: high for the person's own address; medium for careers, or generic with a person; low for generic alone.
- [ ] **Step 5:** run `.venv/bin/pytest tests/contacts -q --deselect tests/contacts/test_measurement.py --deselect tests/contacts/test_cli.py`. Expected: all pass.
- [ ] **Step 6:** commit `feat: propose the person matching the student's target role`.

### Task 4: measuring accuracy and coverage

**Files:**
- Modify: `src/kaltstart/contacts/measurement.py`, `src/kaltstart/contacts/__main__.py`
- Test: `tests/contacts/test_measurement.py`, `tests/contacts/test_cli.py`

**Interfaces:**
- Produces:
  - `RESULT_COLUMNS = ("company_id", "name", "website", "size_category", "pages_fetched", "emails", "people", "contact_address", "contact_person", "confidence", "failure", "email_check", "people_check", "notes")`. `people` holds `name|title|categories|level|source_url` entries joined by ` ; `, with categories joined by `+`.
  - `CONTACT_THRESHOLD = 0.65`, `ACCURACY_THRESHOLD = 0.9`, `COVERAGE_THRESHOLD = 0.4`.
  - `verdict(count, n, threshold)` unchanged.
  - `summarise(rows)`: the lines below.
  - `check_problems(rows)`: also returns one message for a file without the `people` or `people_check` column.

- [ ] **Step 1:** adapt `tests/contacts/test_measurement.py` (columns, `people_check`), and replace the founder lines of `test_summarise_rates_and_mistakes`. With its 20 rows (9 lists reported: 8 confirmed, 1 wrong; 3 missed; 8 none), the text must contain:
  - `People, accuracy: 8/9 lists right (89%)`
  - `People, coverage: 8/20 (40%)`
  - `wrong people list: 1`, `missed people: 3`
  - `People accuracy (threshold 90%, blocking): inconclusive`
  - `People coverage (threshold 40%, goal): inconclusive`
  - one line per category with the number of companies where the scraper reported a person of that category: `leadership: N`, `product: N`, and so on for the seven.
  Add `test_summarise_with_no_people_reported`: accuracy is shown as `0/0 lists right` and its verdict is `fail`.
  Add `test_check_problems_rejects_old_results_files` (Review Focus 5): rows with `founders` and `founder_check` columns give a single message containing `people`.
- [ ] **Step 2:** adapt `tests/contacts/test_cli.py`: the printed lines are `Usable contact (reported): a/n (p%)` and `People (reported): a/n (p%)`; the verification guide names `people_check`. Add `test_summary_refuses_an_old_results_file`: exit 1, the message contains `people`.
- [ ] **Step 3:** run `.venv/bin/pytest tests/contacts -q`. Expected: the measurement and CLI tests fail.
- [ ] **Step 4:** implement. The accuracy verdict is `verdict(confirmed, confirmed + wrong, ACCURACY_THRESHOLD)`, and `fail` when no list was reported; the coverage verdict is `verdict(confirmed, n, COVERAGE_THRESHOLD)`. `measure` scrapes without a target role.
- [ ] **Step 5:** run `.venv/bin/pytest -q -W error`. Expected: everything passes, no warning.
- [ ] **Step 6:** commit `feat: measure people accuracy and coverage`.

### Task 5: documents

**Files:**
- Modify: `docs/superpowers/specs/2026-11-11-kaltstart-design.md`, `docs/superpowers/specs/2026-11-12-phase-2-contact-measurement-design.md`, `DECISIONS.md`, `PRD.md`, `README.md`, `CHANGELOG.md`, `CLAUDE.md`

- [ ] **Step 1:** apply section 10 of the spec to the parent spec: section 2 (the two criteria in place of "name of a founder, 40 %"), 6.1 (`contacts` columns), 6.5 (personal-data rules), 7.2 (people, address types, the table of who is proposed, confidence), 7.4 (one mail per person and per student). Where a rule is replaced, the new text states the rule only; the history is in `DECISIONS.md`.
- [ ] **Step 2:** in the contact-measurement spec, mark sections 5.4, 5.5 and 6 as superseded by the people design, with a link, and leave their text.
- [ ] **Step 3:** `DECISIONS.md`: add D43 to D50, the eight rows of section 11 of the spec, in that order. `PRD.md`: the success metrics and the contact rule. `CLAUDE.md`: the constraints of this plan that are new (people kept, personal-data rules, thresholds). `CHANGELOG.md`: one entry under Unreleased. `README.md`: one sentence saying the scraper now reads people with their job title and is to be measured again.
- [ ] **Step 4:** run `.venv/bin/pytest -q -W error`, then `grep -rn "founder" src/kaltstart/contacts` and check every remaining occurrence is a job-title word or a comment about history. Commit `docs: align specs and decisions with the people design`.

### Task 6: tuning on the companies already seen

No verdict comes from this task: the rules are adjusted while looking at these companies.

- [ ] **Step 1:** run `measure` on the four sample files, to `local/phase-2-people-tuning-1.csv` to `-4.csv` (about 40 minutes in all, in the background).
- [ ] **Step 2:** compare with the verification notes of the earlier results files in `local/`: for each company where a founder was confirmed before, the same person must still be there; for each company where the list was wrong before, read why. List in `local/phase-2-people-tuning.md`, without committing it: people reported per company, anything that looks wrong, anything expected and absent.
- [ ] **Step 3:** for each wrong or absent case with a cause that is general (not one site's quirk), write an invented-page test that reproduces it, see it fail, fix it, run the whole suite. One round only: a second round would be fitting the rules to these 80 companies.
- [ ] **Step 4:** commit the fixes with messages that say what was seen. Record in `DECISIONS.md` what was changed and what was deliberately left.

### Task 7: the verdict

Steps marked **[Owner]** need the project owner.

- [ ] **Step 1 [Owner]:** agree to push `main`, so that the sample command on GitHub sees the earlier sample files.
- [ ] **Step 2:** draw sample 5: `gh workflow run nightly -f command=sample -f args="--seed 2030 --exclude-file docs/measurements/phase-2-sample.csv --exclude-file docs/measurements/phase-2-sample-2.csv --exclude-file docs/measurements/phase-2-sample-3.csv --exclude-file docs/measurements/phase-2-sample-4.csv"`. Save it as `docs/measurements/phase-2-sample-5.csv`, commit and push. Draw sample 6 the same way with seed 2031, also excluding sample 5.
- [ ] **Step 3:** from this point the code is frozen. Run `measure` on both samples, to `local/phase-2-results-5.csv` and `-6.csv`.
- [ ] **Step 4:** first verification pass on the 40 companies, with the cheapest model and a browser that renders JavaScript: `email_check` and `people_check` on every row, `notes` saying why for every `wrong` and `missed`.
- [ ] **Step 5 [Owner]:** check 5 companies of each sample, drawn with `random.Random(2030).sample(range(20), 5)` and `random.Random(2031).sample(range(20), 5)`. A disagreement on one of them means that sample is checked again in full.
- [ ] **Step 6:** run `summary` on the 40 rows together. Read the three verdicts: usable contact (65 %), people accuracy (90 %, blocking), people coverage (40 %, goal).
- [ ] **Step 7:** record the result in `DECISIONS.md`, `README.md` and `CHANGELOG.md`, commit the two summaries. If accuracy is inconclusive, draw 20 more companies with seed 2032 before deciding.
- [ ] **Step 8 [Owner]:** decide the next step: the second plan of Phase 2 (nightly run, `contacts` table, removal on request) if accuracy passes; otherwise people read by the scraper are not shown, and the second plan stores addresses only.
