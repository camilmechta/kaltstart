# Operating Kaltstart

How to run, deploy and maintain Kaltstart. The [README](../README.md) says what it is.

## Run it locally

Try it on your machine with invented companies and fake accounts, without
any key (invitation code `dev`):

```
python -m kaltstart.api --dev
```

## Deploy

Deploy it with the `Dockerfile` on any host that runs a container, with
these environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`SUPABASE_ANON_KEY`, `SESSION_SECRET` (a long random string),
`REMOVAL_CONTACT` (the address shown for removal requests) and
`PROXY_HOPS` (how many proxies of the host stand in front of the app, 1 by
default, so that the sign-up and sign-in limits read the real client
address). The image installs the exact versions of `requirements.txt` and
runs as an unprivileged user. The live app uses `render.yaml` on Render,
which deploys `main` once the checks pass. Before the first sign-up, apply the migrations `0001` to `0009` in the Supabase SQL editor, check
them with `supabase/check_migrations.sql` (every column must be true),
then create single-use invitation codes there; they are shown once:

```sql
select * from create_invitation_codes(20);
```

## Install and test

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

## Ingestion

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

Addresses are stored in `contact_emails`, people in `contact_people`. A
person is a suggestion: the app shows the name, the title and the page it
was read on, and the student confirms it before it is used.

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

## Checking the SQL locally

The migrations and their functions run on a throwaway local PostgreSQL, with
invented data only, never the production database:

```
pip install -e ".[dev,sql]"
pytest -q tests/sql
```

The local server imitates the parts of Supabase the migrations need (roles,
`auth.users`, two pgcrypto functions); what it cannot show is listed in
decision D87.
