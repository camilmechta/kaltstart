"""The migration is applied by hand in the Supabase SQL editor: no test reaches
the database. These checks only keep the file in step with the code."""

import re
from pathlib import Path

from kaltstart.contacts.scrape import FAILURES
from kaltstart.contacts.store import CANDIDATE_COLUMNS

SQL = (Path(__file__).parents[2] / "supabase" / "migrations" / "0002_contacts.sql").read_text()
TABLES = ("contact_emails", "contact_people", "contact_exclusions", "contact_runs")


def test_tables_are_created_and_closed():
    for table in TABLES:
        assert f"create table {table} (" in SQL
        assert f"alter table {table} enable row level security;" in SQL
    assert "create policy" not in SQL.lower()


def test_reading_state_columns_are_added_to_companies():
    for column in CANDIDATE_COLUMNS:
        if column.startswith("contacts_"):
            assert re.search(rf"add column {column} ", SQL), column


def test_every_outcome_the_scraper_reports_is_allowed():
    for outcome in ("ok", *FAILURES):
        assert f"'{outcome}'" in SQL, outcome


def test_removal_functions_exist_and_are_not_public():
    for function in ("exclude_company(p_company_id text)",
                     "exclude_person(p_company_id text, p_person_name text)"):
        assert f"create function {function}" in SQL
        # Supabase lets its API roles call any function of the public schema by
        # default: without this, anybody with the public key could exclude a company.
        assert f"revoke all on function {function} from public, anon, authenticated" in SQL
    # The same key as exclusions.person_key: id, line break, normalised name.
    assert "sha256(convert_to(" in SQL and r"regexp_replace(btrim(" in SQL
