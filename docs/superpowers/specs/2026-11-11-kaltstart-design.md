# Kaltstart: design specification

Date: 2026-11-11
Status: validated
Project name: Kaltstart

## 1. Summary

Kaltstart is a web app reserved for students of the University of St. Gallen
(HSG), by invitation. It finds tech startups and scale-ups in Switzerland,
Germany and Austria that raised funds in the last 12 months, finds who to
write to, and prepares a spontaneous application that opens on the funding
round. The student reviews it and sends it from their own mailbox. The app
never sends anything.

The product does not list job offers. Its difference is the well-targeted
spontaneous application, at the moment the company has just received money to
hire.

## 2. Goals and success criteria

The project is first a product builder portfolio. It becomes a real product
only if the final test reaches thresholds set in advance.

| Criterion | Threshold | Measured in |
|---|---|---|
| Usable contacts found by the scraper | 70 % of companies | Phase 2 |
| Name of a founder found | 40 % of companies | Phase 2 |
| Human reply rate | 10 % of mails sent | Phase 5 |
| Positive reply rate | 3 % of mails sent | Phase 5 |

Definitions:

- **Usable contact**: at least one email address published on the company's
  website, whatever its type.
- **Human reply**: any reply written by a person, including a refusal.
  Automatic acknowledgements do not count.
- **Positive reply**: an offer of a call or an interview.
- **Mail sent**: a mail the student marked as "sent". Mails "presumed sent"
  (see 7.4) are excluded from the rate calculation.

Target volume for the test: 20 students, about 10 mails each, so about 200
mails. The thresholds correspond to 20 human replies, 6 of them positive.

If a Phase 2 threshold is not reached, we stop and choose a plan B before
continuing: manual entry of the missing contacts for the test, reading
JavaScript pages with a real browser, or using the contact form.

## 3. Out of scope

- Automatic sending of mails.
- Reading the students' mailboxes.
- Storing CVs or attachments.
- Scraping LinkedIn.
- Email addresses guessed from a name.
- Calls to an AI API at runtime.
- Other European countries. The geographic scope is Switzerland, Germany and
  Austria; other countries may be added later.
- Requests other than internship or part-time work (first job, simple call).
- Job offers.

## 4. Constraints

- The whole product is in Python, with no AI at runtime: rules, text
  extraction and templates.
- Source of funding rounds: Tech.eu Funding Explorer API, licence CC BY 4.0,
  with the mention "Tech.eu Funding Explorer" required in the app and the
  README.
- Tech.eu quotas: 120 requests per minute, 600 per hour, 2000 per day.
- Scraping: respect robots.txt, limited rate, public pages only.
- Personal data: we store the minimum, and every contact has a source.

## 5. Architecture

Five independent parts. They communicate only through the database, except
the server, which calls the generator directly.

```
Tech.eu API ──> [1. Ingestion] ──┐
                                 ▼
Websites ────> [2. Contacts] ──> Supabase <──> [5. Front]
                                 ▲                 │
               [3. Generator] ── [4. Server] <─────┘
```

| Part | Role | When it runs | Depends on |
|---|---|---|---|
| 1. Ingestion | Fetches new funding rounds, cleans them, writes to the database | Every night, GitHub Actions | Tech.eu API, Supabase |
| 2. Contacts | Visits the websites of companies without a contact, extracts addresses and names | Every night, after ingestion | Websites, Supabase |
| 3. Generator | Pure function: receives profile, company, round, contact; returns subject and body | Called by the server | Nothing external |
| 4. Server | Checks the reservation rules, calls the generator, saves the mail | On every click on "Generate" | Supabase, part 3 |
| 5. Front | Sign-up, filters, list, company page, tracking | In the browser | Supabase, part 4 |

Principles:

1. Cleaning is separate from downloading. The raw Tech.eu response is kept;
   cleaning can be replayed without calling the API again.
2. The generator touches neither the database nor the network. Same inputs,
   same mail.
3. Business rules are checked by the server, never by the front alone.

Technologies: Python, Supabase (Postgres), Jinja2 for the templates, FastAPI
for the server, pytest for the tests, GitHub Actions for the nightly work and
for running the tests on every commit. The choice of tool for the front
(Lovable or a hand-written front) is postponed to the start of Phase 4.

Repository structure:

```
src/kaltstart/ingestion/    src/kaltstart/contacts/
src/kaltstart/mailgen/      src/kaltstart/api/
supabase/migrations/        tests/        docs/        .github/workflows/
PRD.md  DECISIONS.md  CHANGELOG.md  CLAUDE.md  README.md
```

## 6. Data

Seven tables, plus a technical table `sync_runs` that keeps the summary of
each nightly run.

### 6.1 Company data (written by the nightly scripts)

| Table | One row represents | Main columns |
|---|---|---|
| `raw_rounds` | A funding round as Tech.eu returned it | Tech.eu identifier, raw response, retrieval date |
| `companies` | A company | Tech.eu identifier, name, website, description, country, cleaned city, canton or region, sectors |
| `rounds` | A cleaned funding round | company, amount in euros, original stage, size category, date, investors, source link |
| `contacts` | An address or a name found on the website | company, type (personal, careers, generic), address, founder's name and role, source page, confidence, verification date |

The `companies` table also carries the scraping state of each company: never
visited, succeeded, or failed with its reason, the number of attempts and the
date of the next attempt.

### 6.2 Student data (written by the front and the server)

| Table | One row represents | Main columns |
|---|---|---|
| `profiles` | A student | email address, first and last name, degree programme, languages, target role, type of request, availability (start date, duration or workload), preferred sectors and locations |
| `experiences` | A concrete example from the student (two at most) | student, text in English, text in German, order |
| `emails` | A generated mail | student, company, round, contact, template style used, subject, body, language, status, date of each status change |

### 6.3 Size category

Tech.eu classifies about half of the rounds as stage "Other". We therefore
compute a category with three values, stored next to the original stage:

| Category | If the stage is known | Otherwise, by amount |
|---|---|---|
| Small | Pre-seed, Seed | Less than 7 million euros |
| Medium | Series A | From 7 to 20 million euros |
| Large | Series B and beyond | More than 20 million euros |

The stages `Grant` and `Debt` are treated like `Other`: the category comes
from the amount. `Series C`, `Series D+` and `Growth/Late` are "large".

The bounds of 7 and 20 million were calibrated in Phase 1 on the rounds for
which both the stage and the amount are known (decision D22 in DECISIONS.md);
the starting values were 3 and 15 million. A round with neither a known
stage nor an amount is classified "small" by default, and its mail uses an
opening without an amount.

### 6.4 Statuses of a mail

```
generated ──> copied ──> sent ──> human reply ──> positive reply
   └────────────┴──> abandoned
   └────────────┴──> presumed sent   (automatic after 7 days)
```

The `emails` table is enough to compute the cap per company, the limit of
pending mails and the reply rates. There is no reservations table.

### 6.5 Access and data protection

- Supabase Row Level Security: a student reads and modifies only their own
  profile, examples and mails.
- For the cap, they see a number of taken slots per company, never the
  identity of the other students.
- Sign-up with any email address, provided an invitation code is entered. The
  code is the same for the whole test, distributed by the project owner to
  HSG students, and checked by the server. There is no check on the domain of
  the address.
- A student can delete their account and all their data.
- Company contacts come only from public pages and keep their source page.

## 7. Business rules

### 7.1 Ingestion

- First run: 12 months of rounds for Switzerland, Germany and Austria, in
  pages of 100, then one request per company for its record. About 830
  rounds. The rate is limited to stay under 600 requests per hour.
- Every night: we query the Tech.eu `/changes` endpoint, designed for
  synchronisation, with the date of the last successful run minus one day of
  margin. It returns the rounds added and the rounds removed. A round already
  known is updated, never duplicated. The record of a company already known
  is not requested again.
- On every call to `/rounds`, we compare `appliedFilters` with the filters
  sent. If they differ, the script stops with an error and writes nothing.
  `/changes` does not return `appliedFilters`: there we filter the countries
  ourselves.
- City cleaning: removal of extra spaces, then a hand-written mapping table
  (spelling variants brought back to a single name, cantons and regions taken
  out of the city field). Any unknown value is listed in a report, not
  corrected silently.
- Tech.eu already provides each amount in euros (`amountEur`). We store it as
  is, with the original amount and currency.

### 7.2 Contacts

- Pages visited: the home page, then links found on it for the legal notice,
  contact, team and about, and careers pages, with fixed paths as a fallback.
  Eight pages at most per company.
- Politeness: read robots.txt before any visit, at least two seconds between
  two requests to the same site, no project name in the `User-Agent` header
  (decision D27).
  Never LinkedIn.
- Addresses: extracted from text and links, including the common disguised
  forms ("hello [at] startup.ch"). We keep only those on the company's
  domain.
- Founder names: spotted through role words (Founder, Co-Founder, CEO,
  Gründer, Mitgründer, Geschäftsführer) close to a name, on the team and
  Impressum pages.
- Address types: personal (carries the last name of a founder found, or is exactly
  the first name), careers (careers@, jobs@, talent@, hr@), generic (hello@, info@,
  contact@ and equivalents).

Choice of the contact offered to the student:

| Size category | 1st choice | 2nd choice | 3rd choice |
|---|---|---|---|
| Small | Published personal address of a founder | Generic or careers, mail addressed to the founder by first name | Generic or careers alone |
| Medium, large | Careers address | Generic | None |

Confidence level:

| Level | Case |
|---|---|
| High | Published personal address |
| Medium | Careers address, or generic with a founder's name found |
| Low | Generic alone |

A company without any address is hidden from the student list.

### 7.3 Mail generation

- Language: German if the student speaks it and the company is in Germany, in
  Austria or in a German-speaking canton; English otherwise. The student can
  switch. The first version offers only English and German.
- Structure: a mix of fixed blocks and parts that vary with the template
  style. The starting blocks are: opening on the round, sentence about the
  sector, concrete example from the student, paragraph about the role,
  request, signature. The exact split between what is common to all styles
  and what changes from one style to another is not decided yet: it will be
  in Phase 3, with the models provided.
- Opening: depends on the size category, with amount, date and lead investor.
  Three wordings per category. The choice is determined by the
  student-company pair: regenerating gives the same text, and two students
  receive different wordings.
- Missing data: each opening has a version without an amount and a version
  without an investor. No sentence may contain a gap. If the company's sector
  has no dedicated sentence, the sector sentence is omitted.
- Concrete example: the first by default; the student can choose the second.
  Each example is 200 characters at most.
- Role paragraph: one per role (product, growth, data, ops, BD).
- Request: internship (start date, duration) or part-time work (start date,
  workload).
- Signature: first name, last name, HSG degree programme, availability.
- Length: 150 words at most for the body, 60 characters at most for the
  subject.
- Template styles: the student will be able to choose between several mail
  styles (three at most), each in English and in German. The styles will be
  defined in Phase 3 from the models provided by the project owner, of which
  we take the structure and not the text. The style used is saved with each
  mail, to compare reply rates by style in the Phase 5 report. The rules
  above (missing data, lengths, variants) apply to all styles.
- If a required piece of data is missing (first name, degree programme, start
  date, contact address), the generator refuses with a message that names the
  data.

### 7.4 Reservation and tracking

Generating a mail reserves a slot. Generation is refused if:

- the company already has 3 non-abandoned mails created in the last 30 days,
  all students combined;
- the student already has 5 mails with status generated or copied;
- the student already has a non-abandoned mail for this company.

The refusal states the reason and, for the company cap, the date on which a
slot becomes free.

Tracking:

- The front offers three "Copy" buttons: address, subject, body. Copying the
  body moves the mail to status copied.
- The student marks sent, human reply, positive reply or abandoned
  themselves.
- 72 hours after generation without status sent or abandoned, the app shows a
  reminder.
- 7 days after generation, a mail still at status generated or copied moves
  to presumed sent. It counts towards the company cap, no longer counts in
  the limit of 5, and is excluded from the reply rate calculation.

## 8. Error handling

| Situation | Reaction |
|---|---|
| Tech.eu does not answer or the quota is reached | Three spaced attempts, then a clean stop. The one-day margin catches up the following night. |
| `appliedFilters` does not match | Immediate stop, nothing is written. |
| Site slow, in error or forbidden by robots.txt | Reason recorded, move to the next one. New attempt 7 days later, three times at most. |
| Company without a contact | Hidden from the student list. |
| Required data missing for a mail | Refusal with a clear message. |
| Nightly script failure | Email notification from GitHub Actions. |

Each nightly run writes a summary: rounds added and updated, sites visited,
contacts found, errors by type.

## 9. Tests

Test-driven development: the test is written before the code. No test makes a
real network call.

| Part | What is tested | Means |
|---|---|---|
| Ingestion | Pagination, no duplicates, stop if a filter is ignored, city cleaning, size category | Tech.eu responses recorded in files |
| Contacts | Extraction of addresses and names, respect of robots.txt, choice of contact, confidence | Saved HTML pages |
| Generator | No empty variable, no missing amount displayed, lengths, English and German | All combinations of size × role × language × request × missing data (240 cases per template style) |
| Server | The three refusals of 7.4, the move to presumed sent | Test database with fictitious data |

Phase 2 measurement: 20 Swiss companies drawn at random from the rounds in
the database. Result as a table per site (generic address, founder's name,
personal address, cause of failure). Each row is checked by hand to also
count the scraper's mistakes.

## 10. Phases

| Phase | Content | Done when |
|---|---|---|
| 0. Framing | Spec, PRD.md, repo, CLAUDE.md, structure | The spec is validated |
| 1. Ingestion | Tech.eu to Supabase for the three countries, cleaning, incremental update | The rounds are in the database, clean; a second run adds only what is new |
| 2. Contacts | Scraper tested on 20 Swiss sites | The rates are measured and compared with the 70 % and 40 % thresholds |
| 3. Mails | Generator and templates in English and German | All test cases pass, for each style |
| 4. Front | FastAPI server, sign-up with invitation code, filters, list, company page, tracking | A student goes from sign-up to a copied mail without help |
| 5. Test | 20 HSG students, about 200 mails | Report comparing the rates with the 10 % and 3 % thresholds |

Each phase has its own implementation plan and ends with a code review.
Phase 1 is planned first.

## 11. Decision log

| # | Decision | Reason | Options set aside |
|---|---|---|---|
| D1 | Portfolio first, continuation conditional on the thresholds | A threshold set before the test shows a product approach | Portfolio only; real product from the start |
| D2 | Thresholds of 10 % human replies and 3 % positive | Above a generic mail, enough volume to conclude | 5 %; 15 % |
| D3 | Request limited to internship or part-time work | Precise request, comparable test | Internship only; any type of request |
| D4 | One or two concrete examples entered by the student | The only part that distinguishes one student from another, without AI | Structured fields only; one example per role |
| D5 | 3 mails per company over 30 days, counted at generation | Protects the founder; the app necessarily sees the generation | No limit; counter without blocking; counting at declared sending |
| D6 | "Copy" buttons, limit of 5 pending mails | Matches real usage; pushes students to keep tracking up to date | `mailto:` button; address in blind copy |
| D7 | Personal address only if published | Every address has a verifiable source; no bounce | Always generic; guessed address |
| D8 | Scraper thresholds at 70 % and 40 % | Checkpoint before investing in Phases 3 to 5 | 50 %; 85 % |
| D9 | FastAPI for generation, GitHub Actions for the night | The Python must run on click; the nightly work does not need a server | Queue in the database; templates rewritten in JavaScript |
| D10 | Presumed-sent mails excluded from the rates | We do not know whether they left; they would distort the metric | Count them as sent |
| D11 | Sign-up with invitation code, no domain check | Simpler, no dependency on university mailboxes, control over who gets in | HSG address required; open sign-up |
| D12 | Several template styles, style saved per mail | The student picks the tone that suits them; the test compares styles | A single template |
| D13 | Public repository documents in English (README, PRD, DECISIONS, CHANGELOG, CLAUDE.md, code and commits) | Readable by European tech recruiters | French |

## 12. Open questions

They do not block Phase 1.

- Exact content of the template styles (to be defined in Phase 3, from the
  models provided).
- Split between fixed structure and template styles (Phase 3).
- Front tool: Lovable or a hand-written front (to be decided in Phase 4).
- Host for the FastAPI server (to be decided in Phase 4).
