# Phase 2: contact scraper and measurement, design

Date: 2026-11-12
Status: awaiting review
Parent spec: `docs/superpowers/specs/2026-11-11-kaltstart-design.md` (sections 2, 7.2, 8 and 9)

## 1. Purpose

Phase 2 answers one question before anything else is built on top of it: can
a simple program find, on a company's own website, someone to write to?

The phase builds the contact scraper and measures it on 20 Swiss companies.
The measurement is a checkpoint. If it reaches the thresholds, a second plan
adds the nightly run and the database writes. If it does not, the project
stops and a plan B is chosen (parent spec, section 2).

Success criteria, from the parent spec:

| Criterion | Threshold |
|---|---|
| Companies with a usable contact | 70 % |
| Companies with the name of a founder | 40 % |

- **Usable contact**: at least one email address published on the company's
  website, on the company's own domain, whatever its type.
- **Name of a founder**: the full name of one person presented on the site
  with a founder or managing-director role.

Both rates are counted on results **confirmed by hand**, not on what the
scraper reports.

## 2. Scope

In scope:

- The scraper: fetch pages politely, extract addresses and founder names,
  classify addresses, choose the contact to propose.
- A command that draws the sample of 20 companies from the database.
- A command that runs the scraper on a sample file and writes the results.
- The measurement, its verification by hand, and the verdict.

Out of scope, deferred to a later plan that depends on the verdict:

- The nightly run over all companies, and retries after 7 days.
- The `contacts` table and the scraping state on `companies`.
- A real browser for pages that need JavaScript.
- Measuring German and Austrian sites. The scraper handles German pages, but
  the measurement covers Switzerland only, as the parent spec states.

## 3. How the measurement runs

1. **Draw the sample.** `python -m kaltstart.ingestion sample`, run from the
   `nightly` workflow because the database keys live in GitHub. It selects 20
   companies at random among Swiss companies that have a website, with a
   fixed random seed (2026) so the same list can be drawn again; `sample` is
   added to the commands the workflow can run by hand. Output: one CSV row
   per company with `company_id`, `name`, `website`, `size_category`. The size
   category of a company is that of its most recent round.
2. **Run the scraper.** `python -m kaltstart.contacts measure <sample.csv>`,
   run on the project owner's machine. It needs no database access. It
   writes a detailed results file and prints a summary.
3. **Verify by hand.** A first pass visits the 20 sites and records, for each
   company, whether each reported address and name is correct, and whether
   the site publishes an address or a founder name the scraper missed. The
   project owner then confirms the reported finds through their source links
   and checks 5 of the 20 companies independently, drawn at random. If the two
   passes disagree on any of those 5, all 20 are checked again.
4. **Verdict.** The confirmed rates are compared with the thresholds and the
   result is recorded in `DECISIONS.md`.

Twenty companies is a small sample: one company is 5 percentage points. A
result within one company of a threshold (65 % to 75 % for contacts, 35 % to
45 % for founders) is treated as inconclusive, and 20 more companies are
drawn with seed 2027, excluding the first 20, before deciding on all 40.

## 4. What is public and what stays local

The repository is public. Founder names and personal addresses are published
on company sites, but gathering them in one file in a public repository would
publish a ready-made contact list.

| File | Content | Location |
|---|---|---|
| `docs/measurements/phase-2-sample.csv` | company name, website, size category | repository |
| `local/phase-2-results.csv` | addresses and names found, source pages, verification columns | owner's machine only; `local/` is git-ignored |
| `docs/measurements/phase-2-summary.md` | rates, failure causes, scraper error counts; no name, no address | repository |

Test fixtures are invented pages with invented people and the reserved
domains `example.ch`, `example.de` and `example.com`. No real page is copied
into the repository.

## 5. What the scraper does on one site

Five steps, one module each, under `src/kaltstart/contacts/`.

### 5.1 Fetch politely (`fetcher.py`)

- Reads `robots.txt` first and obeys the rules addressed to all robots
  (`User-agent: *`). If the site forbids the home page, nothing is fetched.
  A missing or unreadable `robots.txt` means no restriction.
- Waits at least 2 seconds between two requests to the same site.
- Fetches at most 8 pages per company, home page included.
- Stays on the company's site: same registrable domain as the website in the
  sample, with or without `www`. Links to any other site are ignored. LinkedIn
  is never fetched.
- Reads HTML only, at most 2 MB per page, with a 15-second timeout.
- Does not announce the project: no project name and no link in the
  `User-Agent` header. It uses the HTTP library's default header and does not
  imitate a browser.

### 5.2 Choose the pages (`pages.py`)

The scraper reads the home page, then follows the links found on it whose
text or address contains a keyword, in this priority order:

| Priority | Kind | Keywords |
|---|---|---|
| 1 | Legal notice | impressum, imprint, legal |
| 2 | Contact | contact, kontakt |
| 3 | Team and about | team, about, ueber-uns, über uns, about-us, company, unternehmen |
| 4 | Careers | careers, career, jobs, karriere, join |

At most 7 pages after the home page, at most 2 per kind before moving to the
next kind. If the home page yields no matching link, the scraper tries the
fixed paths of the parent spec (`/impressum`, `/imprint`, `/contact`, `/team`,
`/about`, `/careers`, `/jobs`).

### 5.3 Extract addresses (`emails.py`)

- From `mailto:` links and from the visible text.
- Including common disguised forms: `[at]`, `(at)`, ` at `, `[dot]`, `(dot)`.
- Only addresses on the company's domain are kept. Addresses on another
  domain are counted, not kept (see 5.6).
- Addresses of website tooling are discarded (for example error-tracking or
  site-builder domains, and image file names that look like addresses).

### 5.4 Extract founder names (`founders.py`)

On legal-notice, team and about pages only. The scraper looks for a role word
and takes the person's name next to it, in the same line or the same block of
the page.

Role words: Founder, Co-Founder, Cofounder, CEO, Chief Executive Officer,
Managing Director, Gründer, Gründerin, Mitgründer, Mitgründerin,
Geschäftsführer, Geschäftsführerin, Geschäftsleitung.

A name is two to four capitalised words. A candidate is rejected if it
contains a role word, a company suffix (AG, GmbH, SA, Sàrl, Ltd) or a digit.
This step is the least reliable of the five, which the 40 % threshold
reflects.

### 5.5 Classify and choose (`selection.py`)

The rules of the parent spec, section 7.2, unchanged:

- Address types: personal (the local part contains the first or last name of
  a founder found), careers (`careers@`, `jobs@`, `talent@`, `hr@`,
  `karriere@`, `recruiting@`), generic (everything else).
- Contact proposed, by size category: for small, a founder's personal
  address, else generic or careers with the founder's first name, else generic
  or careers alone; for medium and large, the careers address, else generic,
  else none.
- Confidence: high for a published personal address; medium for a careers
  address, or a generic one with a founder's name; low for a generic address
  alone.

### 5.6 Outcome of one company (`scrape.py`)

One result per company: the addresses kept with their type and source page,
the founder names with their role and source page, the proposed contact with
its confidence, the pages fetched, and, when no usable contact was found, one
failure cause:

| Cause | Meaning |
|---|---|
| `robots_forbidden` | `robots.txt` forbids the home page |
| `unreachable` | no page could be fetched: error, timeout, or refusal |
| `little_text` | pages fetched, but fewer than 200 characters of visible text in total: probably rendered by JavaScript |
| `other_domain_only` | addresses found, none on the company's domain |
| `contact_form_only` | no address, but a fetched page has a form with a message field |
| `no_address` | none of the above |

An error on one company never stops the run: it is recorded as that
company's outcome and the scraper moves to the next one.

## 6. The summary

`docs/measurements/phase-2-summary.md` contains, for the 20 companies:

- the two rates as reported by the scraper, and as confirmed by hand;
- the count of scraper mistakes found by the verification: wrong address,
  wrong founder name, missed address, missed founder name;
- the count of each failure cause;
- the split of proposed contacts by confidence level and by size category;
- the verdict against the two thresholds, or "inconclusive".

## 7. Tests

Test-driven: each test is written and seen failing before the code. No test
makes a real network call.

| Module | What is tested | Means |
|---|---|---|
| `fetcher` | `robots.txt` read first and obeyed, 2-second wait, 8-page limit, same-site rule, timeout and size limit, default `User-Agent` | `httpx.MockTransport` and an injected `sleep` |
| `pages` | priority order, limit per kind, German and English keywords, fallback to fixed paths | invented home pages |
| `emails` | `mailto:` and text, disguised forms, domain rule, tooling addresses discarded | invented pages |
| `founders` | role words in English and German, legal-notice and team layouts, rejections | invented pages |
| `selection` | every row of the contact and confidence tables | direct calls |
| `scrape` | each failure cause; an error on one site does not stop the next | a fake fetcher |
| `sample` command | 20 Swiss companies with a website, same seed gives the same list | `InMemoryStore` |
| `measure` command | results file columns, summary rates | a fake fetcher |

## 8. Decisions

To be added to `DECISIONS.md`:

| Decision | Reason | Options set aside |
|---|---|---|
| Measure the scraper on 20 sites before building the nightly run and the database writes | The measurement is a checkpoint: if it fails, the method changes and anything built around it would be redone | Build the whole phase at once |
| Read the raw HTML of pages, without a browser | Fast, free and simple to run; the measurement shows how many sites need JavaScript | A real browser from the start; a browser as a fallback now |
| Follow the home page's links by keyword, with the fixed paths as a fallback | Sites use many names for the same page, in two languages; guessing paths mostly yields missing pages | Fixed paths only |
| Keep only addresses on the company's domain, and count the others as a failure cause | Protects against addresses of third parties; the count shows whether the rule costs too much | Keep any address found on the site |
| The scraper does not announce the project in its `User-Agent`, and does not imitate a browser | The project owner does not want the repository linked from site logs; pretending to be a browser would work around sites that refuse robots. Replaces "a tool name that identifies the project" in the parent spec | A named bot with a link to the repository; a browser `User-Agent` |
| Detailed results stay on the owner's machine; the repository holds only the sample and a summary without names or addresses | The repository is public; a file of founder names and addresses would be a ready-made contact list | Commit the full results |
| First verification pass by an assistant, then the owner confirms the finds and checks 5 companies independently | Keeps an independent human check at about half an hour of the owner's time | Owner checks all 20; no independent check |
| A result within one company of a threshold is inconclusive and 20 more companies are drawn | One company is 5 percentage points | Decide on 20 whatever the result |
