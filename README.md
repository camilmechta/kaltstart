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
| 1. Ingestion | Tech.eu funding rounds to Supabase | In progress |
| 2. Contacts | Contact scraper | Not started |
| 3. Mails | Mail generator, English and German | Not started |
| 4. Front end | Server and web app | Not started |
| 5. Test | Test with 20 students | Not started |

See [PRD.md](PRD.md) for scope and success metrics and
[DECISIONS.md](DECISIONS.md) for the decision log.

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

## Data

Data: Tech.eu Funding Explorer, CC BY 4.0
(<https://funding.tech.eu/methodology>).
