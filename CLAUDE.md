# CLAUDE.md

Kaltstart ingests startup funding rounds from the Tech.eu Funding Explorer API
into Supabase, finds contacts, and prepares spontaneous application mails for
HSG students. See PRD.md for scope and DECISIONS.md for the decision log.

## Commands

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Ingestion commands (they need `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`; there
are no local credentials, so run them from the `nightly` workflow in GitHub
Actions):

```
python -m kaltstart.ingestion backfill [--months 12]
python -m kaltstart.ingestion sync
python -m kaltstart.ingestion reclean
python -m kaltstart.ingestion report
python -m kaltstart.ingestion cities
```

Contact commands, run from the `contacts` workflow for the same reason:

```
python -m kaltstart.contacts run [--country Switzerland --country Germany --country Austria] [--max 300]
python -m kaltstart.contacts status [--country ...]
```

Web app (Phase 4): `python -m kaltstart.api --dev` runs it locally with
invented data and fake accounts; production runs the `Dockerfile` with the
environment variables listed in the README.

## Constraints

- No call to any AI API at runtime.
- No test makes a real network call. Tech.eu responses are replayed from
  `tests/fixtures/techeu/`.
- Tech.eu quotas: 120 requests per minute, 600 per hour, 2000 per day. The
  client waits 7 seconds between requests and stops at 1500 requests per run.
- Countries covered, with the exact API spelling: `Switzerland`, `Germany`,
  `Austria`.
- The README must credit the source: "Tech.eu Funding Explorer", licence
  CC BY 4.0.
- Every file in the repository is in English: public documents, spec, plans,
  code, comments and commit messages.
- The repository is public and so are its workflow logs: no command, log,
  workflow input or run summary may contain a person's name, an email
  address or a page. Removal on request is done in the Supabase SQL editor.
- No secret in the repository. Supabase keys come from the environment
  variables `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
- Contact scraper: `robots.txt` is read first and obeyed; at least 2 seconds
  between requests to a site; at most 8 pages per company; never LinkedIn or
  any other site; no project name in the `User-Agent`, no browser imitation.
- People kept by the scraper: leaders, heads and managers of seven functions
  (product, growth, data, operations, sales, engineering, R&D) and
  recruiters, read with their
  job title on the company's own site. Never prose, never a testimonial,
  never somebody of another organisation. Only name, title, categories,
  level and source page are kept.
- Thresholds: address found for 75 % of the companies that publish one on a
  site of their own, no wrong address (blocking), people accuracy 90 %
  (tracked, not blocking), people coverage 40 % (a goal).
- A person read by the scraper is a suggestion: the app shows the name, the
  title and the page it was read on, and the student confirms it before it
  is used in a mail. Never used unconfirmed.
- Contact test fixtures are invented pages with invented people on
  `example.ch`, `example.de` and `example.com`. Never commit a real page, name
  or address. Detailed measurement results stay under `local/` (git-ignored).
- Test-driven development: write the test and see it fail before writing the
  code.
- Commit message format: `type: description`.

## Structure

```
src/kaltstart/ingestion/    Tech.eu ingestion (Phase 1)
src/kaltstart/contacts/     contact scraper (Phase 2)
src/kaltstart/mailgen/      mail generator (Phase 3)
src/kaltstart/api/          FastAPI server (Phase 4)
supabase/migrations/        database migrations
tests/                      tests, with fixtures in tests/fixtures/
docs/                       specification and plans
.github/workflows/          CI and nightly jobs
```

`ingestion/` is done (Phase 1). `contacts/` runs every night for the three
countries (Phase 2). `mailgen/` is a pure function with six Jinja2
templates (Phase 3). `api/` is the web app (Phase 4): FastAPI pages, the
reservation rules, Supabase Auth through the server.

## Maintenance

Update DECISIONS.md and CHANGELOG.md with every notable change.
