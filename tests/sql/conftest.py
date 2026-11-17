"""A throwaway local PostgreSQL that runs the real migrations (D87).

Never the production database: the server lives in a temporary folder and
holds invented data only. It imitates what the migrations need from Supabase
(the roles, auth.users, and the two pgcrypto functions of the `extensions`
schema). The tests are skipped when the optional `sql` dependencies are not
installed (`pip install -e ".[dev,sql]"`)."""

import tempfile
from pathlib import Path

import pytest

pgserver = pytest.importorskip("pixeltable_pgserver")
psycopg = pytest.importorskip("psycopg")

MIGRATIONS = sorted((Path(__file__).parents[2] / "supabase" / "migrations").glob("0*.sql"))

SUPABASE_LIKE = """
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;
create schema auth;
create table auth.users (
  id uuid primary key default gen_random_uuid(),
  email text,
  raw_user_meta_data jsonb not null default '{}'
);
create schema extensions;
-- Stand-ins for pgcrypto, which this local server does not ship.
create function extensions.digest(p_data text, p_type text) returns bytea
  language sql immutable as $$ select sha256(convert_to(p_data, 'UTF8')) $$;
create function extensions.gen_random_bytes(p_count int) returns bytea
  language sql volatile as $$
  select decode(substr(md5(random()::text) || md5(random()::text), 1, p_count * 2), 'hex') $$;
"""


@pytest.fixture(scope="session")
def database_uri():
    folder = tempfile.mkdtemp(prefix="kaltstart-pg-")
    server = pgserver.get_server(folder, cleanup_mode="delete")
    uri = server.get_uri()
    with psycopg.connect(uri, autocommit=True) as conn:
        conn.execute(SUPABASE_LIKE)
        for migration in MIGRATIONS:
            conn.execute(migration.read_text())
    yield uri


@pytest.fixture
def db(database_uri):
    """A connection whose changes are rolled back after the test."""
    with psycopg.connect(database_uri) as conn:
        yield conn
        conn.rollback()


def as_role(conn, role: str) -> None:
    conn.execute(f"set local role {role}")
