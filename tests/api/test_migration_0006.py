"""Migration 0006: single-use invitation codes (D86). Applied by hand in the
Supabase SQL editor after 0005; no test reaches the database."""

from pathlib import Path

SQL = (Path(__file__).parents[2] / "supabase" / "migrations" / "0006_invitation_codes.sql").read_text()


def body(name):
    return SQL.split(f"create or replace function {name}", 1)[1].split("$$;", 1)[0]


def test_codes_are_kept_as_fingerprints_only():
    table = SQL.split("create table if not exists invitation_codes (", 1)[1].split(");", 1)[0]
    assert "code_hash text primary key" in table and "used_at timestamptz" in table
    assert "used_by uuid references auth.users(id) on delete set null" in table
    assert " code text" not in table                       # never the code itself
    assert "alter table invitation_codes enable row level security;" in SQL


def test_codes_are_created_by_the_owner_and_shown_once():
    create = body("create_invitation_codes(p_count int)")
    assert "extensions.gen_random_bytes" in create and "extensions.digest" in create
    assert "p_count between 1 and 100" in create
    assert "returns table (code text)" in SQL.split("create or replace function create_invitation_codes", 1)[1][:200]


def test_a_code_is_used_once_when_the_account_is_created():
    check = body("check_invitation_code()")
    assert "update invitation_codes" in check and "used_at is null" in check
    assert "used_by = new.id" in check and "raise exception" in check
    assert "app_settings" not in check                     # the shared code is no longer accepted
    assert "after insert on auth.users" in SQL             # new.id exists for the reference
    assert "drop trigger if exists check_invitation_code on auth.users;" in SQL


def test_the_app_can_ask_without_using_a_code():
    ok = body("invitation_code_ok(p_code text)")
    assert "used_at is null" in ok and "update" not in ok


def test_no_function_is_open_to_the_public():
    for function in ("create_invitation_codes(int)", "invitation_code_ok(text)",
                     "cancel_invitation_code(text)", "check_invitation_code()"):
        assert f"revoke all on function {function} from public, anon, authenticated;" in SQL, function
