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
| 2. Contacts | Contact scraper | In progress |
| 3. Mails | Mail generator, English and German | Not started |
| 4. Front end | Server and web app | Not started |
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

The contact scraper is measured on Swiss companies drawn at random, with every
result checked by hand. Samples and summaries are in
[docs/measurements](docs/measurements); they contain no name and no address.

| Confirmed | First run, 20 companies | Second run, 20 new companies | Threshold |
|---|---|---|---|
| Company with a usable address | 13 (65 %) | 13 (65 %) | 65 % (was 70 %) |
| Company with a founder's name | 1 (5 %) | 6 (30 %) | 40 % |

Founder extraction was rewritten between the two runs, from the failures of
the first one. No address reported by the scraper was wrong in either run.
Both thresholds are still missed, mostly on pages the scraper cannot see
(built by JavaScript) and on customer testimonials taken for team members.
The nightly run is not built until this is resolved.

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

## Data

Data: Tech.eu Funding Explorer, CC BY 4.0
(<https://funding.tech.eu/methodology>).
