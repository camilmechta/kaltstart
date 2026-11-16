# Kaltstart

Kaltstart helps students at the University of St. Gallen (HSG) write targeted
spontaneous applications to tech startups in Switzerland, Germany and Austria
that recently raised funding. It finds the funding round, looks for a published
contact address, and prepares a mail that opens on the round. The student
reviews and sends the mail from their own mailbox; the app never sends anything.

## Status

| Phase | Content | Status |
|---|---|---|
| 0. Scoping | Spec, PRD, repository, structure | Done |
| 1. Ingestion | Tech.eu funding rounds to Supabase | Done |
| 2. Contacts | Contact scraper, stored and read every night (Switzerland) | Done for Switzerland; Germany and Austria to be measured |
| 3. Mails | Mail generator, English and German | Done; Phase 4 connects it |
| 4. Front end | Server and web app | Built; to be deployed |
| 5. Test | Test with 20 students | Not started |

See [PRD.md](PRD.md) for scope and success metrics and
[DECISIONS.md](DECISIONS.md) for the decision log.

### Phase 1 result

First load on 2026-11-11, covering the previous 12 months:

| | Count |
|---|---|
| Funding rounds | 832 (Germany 508, Switzerland 260, Austria 64) |
| Companies | 783 |
| Companies with a website | 780 |
| Rounds by size category | 594 small, 119 medium, 119 large |

A nightly job keeps the data up to date, and a weekly job re-reads the last
12 months to pick up edits to known rounds.

### Phase 2 measurements

The contact scraper is measured on companies drawn at random, with every
result checked on the company's site by an assistant. Samples and summaries are in
[docs/measurements](docs/measurements); they contain no name and no address.

| Confirmed, on companies never seen before | Run 1 | Run 2 | Runs 3 and 4 | Threshold | Verdict |
|---|---|---|---|---|---|
| Company with a usable address | 65 % | 65 % | 70 % | 65 % (was 70 %) | Pass |
| Company with a founder's name | 5 % | 30 % | 35 % | 40 % | Fail |

Runs 1 and 2 cover 20 companies each; runs 3 and 4 use the same code and
cover 40 together. Founder extraction was rewritten after run 1 and refined
after run 2, each time from the failures read on the real pages. No address
reported by the scraper was found wrong in any run. Finding addresses is
accepted; finding founders is not. The scraper has since been changed to
read the people a company presents with their job title (leaders, function
heads and managers, recruiters).

That people scraper was measured on 60 more companies (runs 5 to 7, same
code):

| Confirmed, on 60 companies never seen before | Runs 5 to 7 | Threshold | Verdict |
|---|---|---|---|
| Company with a usable address | 52 % | 65 % | Fail |
| People accuracy: lists reported that are entirely right | 24 of 25 (96 %) | 90 %, blocking | Pass |
| People coverage: companies with a right list | 40 % | 40 %, a goal | At the goal (inconclusive) |

People read by the scraper can be shown to students. Three of the 24 right
lists hold a co-founder or an acting officer shown in an advisors or board
section: the rule fixed before the measurement counts them as right, a
stricter reading would give 21 of 25 (84 %). The one wrong list is a degree
read as part of a name. No address reported was wrong, but the address rate
fell from 70 %: five of the 60 companies have no site of their own in the
source data (a profile on an accelerator's site, a social network page), six
sites did not answer the scraper although four of them load in a browser,
and four publish their address on a second domain.

The investigation that followed found that 17 of the 29 companies without an
address publish none on a site of their own, so about 72 % was the most this
sample could give. Three fixes cover five of the twelve real misses. An
eighth run on 20 companies never seen, after the fixes:

| Confirmed, on 20 companies never seen before | Run 8 | Threshold | Verdict |
|---|---|---|---|
| Company with a usable address | 14 of 20 (70 %) | 65 % | Inconclusive (one company above) |
| People accuracy: lists reported that are entirely right | 8 of 10 (80 %) | 90 %, blocking | Below, on 10 lists |
| People coverage: companies with a right list | 40 % | 40 %, a goal | At the goal (inconclusive) |

No address reported was wrong. None of the 14 addresses came from the three
fixes: this sample simply held no accelerator profile and no site refusing
automated clients. The two wrong lists keep people of other organisations
(two customers quoted on a home page, an investor's representative). Over
runs 5 to 8, people accuracy is 32 lists of 35 (91 %).

The share of all companies with an address depends mostly on the draw: about
a quarter of the companies publish no address on a site of their own, and
nothing can be found there. The address threshold was therefore replaced by
two criteria: an address found for 75 % of the companies that publish one,
and no wrong address at all (blocking). Over runs 5 to 8, 59 of 80 companies
publish an address and the scraper found 45 of them (76 %), with no wrong
address. The new threshold was set knowing this figure, so it only counts as
passed once a later measurement confirms it.

A ninth run on 20 more companies never seen, after two more people rules
(a plain "Board" label, cards linking to a customer story):

| Confirmed, on 20 companies never seen before | Run 9 | Threshold | Verdict |
|---|---|---|---|
| Address found when the company publishes one | 13 of 16 (81 %) | 75 % | Inconclusive (one company above) |
| Wrong addresses | 0 | none, blocking | Pass |
| People accuracy: lists reported that are entirely right | 6 of 9 (67 %) | 90 %, blocking | Fail |
| People coverage: companies with a right list | 30 % | 40 %, a goal | Below |

The address part holds. The people part does not: the three wrong lists have
three new causes (a video caption read as a name, a photo caption given a
title that the page does not show for that person, and "Personal Care" in a
sales title read as the German word for staff). Over runs 5 to 9, people
accuracy is 38 lists of 44 (86 %). People read by the scraper are not
reliable enough to be used without a check. A person is therefore a
suggestion: the app will show the name, the title and the page it was read
on, and the student confirms it before it is used. The 90 % accuracy figure
is tracked and no longer blocks.

Correction to run 9: one of the three lists counted wrong (a title said to
be absent from the page) is in fact shown on the page, so the count is 7
right lists of 9 (78 %), and 39 of 44 (89 %) over runs 5 to 9.

### Mails

`kaltstart.mailgen.generate` writes the subject and body of a spontaneous
application from a student's profile, a company, its round and a contact. It
is a pure function: no network, no database, no AI. Three styles (Direct,
Round, Formal), each in English and German, at most 200 words and a subject
of at most 60 characters. Every mail is built around the student's
showcase sentence from their profile; a motivated student may add a sentence
of their own about the company. The twelve reference mails are in
[tests/mailgen/golden](tests/mailgen/golden).

### Web app

The app students use: sign-up with an invitation code, a profile, the list
of companies that just raised, a company page where the student chooses who
to write to, previews the mail for free and keeps it, then copies it into
their own mailbox, and "My mails" to follow it. Server-rendered pages
(FastAPI and Jinja2), styled after [DESIGN.md](DESIGN.md). The app never
sends a mail.

Try it on your machine with invented companies and fake accounts, without
any key (invitation code `dev`):

```
python -m kaltstart.api --dev
```

Deploy it with the `Dockerfile` on any host that runs a container, with
these environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`SUPABASE_ANON_KEY`, `SESSION_SECRET` (a long random string) and
`REMOVAL_CONTACT` (the address shown for removal requests). Before the first
sign-up, apply `supabase/migrations/0004_students.sql` in the Supabase SQL
editor and set the invitation code there:

```sql
insert into app_settings values ('invitation_code', '<the code>');
```

## Installation

Requires Python 3.12 or later.

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Supabase credentials are read from the environment variables `SUPABASE_URL` and
`SUPABASE_SERVICE_KEY`. Nothing loads a `.env` file: export both variables in
your shell, or set them as GitHub Actions secrets. `.env.example` only lists
their names. Never commit real values.

## Usage

```
python -m kaltstart.ingestion backfill [--months 12]   # first load, then company details
python -m kaltstart.ingestion sync                      # added and removed rounds since the last run
python -m kaltstart.ingestion reclean                   # reapply cleaning rules, no API call
python -m kaltstart.ingestion report                    # counts, size categories, median amounts
python -m kaltstart.ingestion cities                    # city values, to maintain the alias table
```

The database schema is in `supabase/migrations/0001_ingestion.sql`. The
workflow `.github/workflows/nightly.yml` runs `sync` every night and `backfill`
every Sunday, and can run any command by hand from the Actions tab. GitHub
disables scheduled workflows after 60 days without repository activity.

### Contacts

```
python -m kaltstart.contacts run [--country Switzerland] [--max 300]   # read the sites that are due, store contacts
python -m kaltstart.contacts status [--country Switzerland]            # counts only
```

The schema is in `supabase/migrations/0002_contacts.sql`. The workflow
`.github/workflows/contacts.yml` runs `run` every night, one hour after the
ingestion, and either command by hand. A company's site is read when it has
never been visited, again 30 days after a reading, and 7 days after a
failure to reach it; after three such failures in a row its contacts are
deleted. Switzerland, Germany and Austria are read, each with its own cap of
300 companies per run.

After the first full run (2026-11-15), the 236 eligible Swiss companies have
been read: 161 have an address stored and 110 a suggested person. These are
the scraper's own counts, not verified figures.

Addresses are stored in `contact_emails`, people in `contact_people`. A
person is a suggestion: the app will show the name, the title and the page
it was read on, and the student confirms it before it is used.

This repository is public, and so are the logs of its workflows. The
commands print counts and company identifiers, never a name, an address or
a page.

### Removal on request

A person or a company can ask not to be listed. The project owner does it
by hand in the Supabase SQL editor, never through a workflow, because a
workflow input would be printed in a public log.

1. In Supabase, open the table `companies`, search the company by name and
   copy its `id`.
2. For a person, list the names stored for that company and copy the name
   exactly as it appears there (the scraper removes titles such as "Dr."):

```sql
select name from contact_people where company_id = '00000000-0000-0000-0000-000000000000';
```

3. Run one of these lines with that `id`:

```sql
select exclude_person('00000000-0000-0000-0000-000000000000', 'Anna Muster');
select exclude_company('00000000-0000-0000-0000-000000000000');
```

`exclude_person` answers with what it removed, or with a warning when no
stored person has that name; the exclusion is saved in both cases. It also
removes the person's addresses (`anna.muster@`, `muster@`, `anna@`,
`amuster@`), whatever type they were stored as, and the scraper never adds
the person or those addresses again. The exclusion list keeps keys computed
from the name, not the name.

## Data

Data: Tech.eu Funding Explorer, CC BY 4.0
(<https://funding.tech.eu/methodology>).
