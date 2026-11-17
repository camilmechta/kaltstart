"""Migration 0004 is applied by hand in the Supabase SQL editor; no test
reaches the database. These checks keep the file in step with the code."""

import re
from pathlib import Path

SQL = (Path(__file__).parents[2] / "supabase" / "migrations" / "0004_students.sql").read_text()
TABLES = ("app_settings", "profiles", "showcases", "mails")


def test_tables_are_created_and_closed():
    for table in TABLES:
        assert f"create table {table} (" in SQL, table
        assert f"alter table {table} enable row level security;" in SQL, table
    assert "create policy" not in SQL.lower()


def test_mails_columns():
    for column in ("student_id uuid references auth.users(id) on delete set null",
                   "person_key text", "person_choice text", "company_line text",
                   "created_at timestamptz", "copied_at timestamptz", "sent_at timestamptz",
                   "human_reply_at timestamptz", "positive_reply_at timestamptz",
                   "abandoned_at timestamptz"):
        assert column in SQL, column
    for status in ("generated", "copied", "sent", "human_reply", "positive_reply", "abandoned"):
        assert f"'{status}'" in SQL
    for choice in ("suggested", "other_on_list", "typed", "team"):
        assert f"'{choice}'" in SQL


def test_reserve_mail_locks_counts_and_names_its_reasons():
    assert re.search(r"create function reserve_mail\(p_student_id uuid, p_company_id text,\s*"
                     r"p_person_key text, p_row jsonb\)\s*returns jsonb", SQL)
    assert "pg_advisory_xact_lock(hashtext(p_company_id))" in SQL
    for reason in ("company_full", "student_pending", "company_done", "person_done"):
        assert f"'{reason}'" in SQL
    assert "make_interval(days => v_cap_days)" in SQL and "make_interval(days => v_speed_days)" in SQL


def test_invitation_code_trigger():
    assert "create function check_invitation_code()" in SQL
    assert "raw_user_meta_data->>'invitation_code'" in SQL
    assert "before insert on auth.users" in SQL
    assert "from app_settings where key = 'invitation_code'" in SQL


def test_removal_functions_also_blank_names_in_mails():
    for function in ("exclude_company(p_company_id text)",
                     "exclude_person(p_company_id text, p_person_name text)"):
        assert f"create or replace function {function}" in SQL
    assert SQL.count("update mails set person_name = null, person_source_url = null") >= 2


def test_new_functions_are_not_public():
    for function in ("reserve_mail(uuid, text, text, jsonb)", "check_invitation_code()",
                     "exclude_company(p_company_id text)",
                     "exclude_person(p_company_id text, p_person_name text)"):
        assert f"revoke all on function {function} from public, anon, authenticated;" in SQL, function


def test_reserve_mail_applies_the_limits_passed_by_the_server():
    body = SQL.split("create function reserve_mail", 1)[1].split("$$;", 1)[0]
    for reason in ("'round_full'", "'student_speed'"):
        assert reason in body, reason
    # The limits come from the server (kaltstart.api.rules.LIMITS), not constants.
    for key in ("company_cap", "cap_days", "round_cap", "speed", "speed_days", "pending"):
        assert f"'{key}'" in body, key
    assert "copied_at is not null" in body
    # Without limits every comparison would be null and nothing refused.
    assert "if v_limits is null then" in body and "raise exception" in body
    assert "p_row->>'size_category'" in body
    assert "variant" in body.split("insert into mails", 1)[1]


def test_mails_store_the_variant_and_the_size():
    assert "variant int not null default 0" in SQL
    assert "size_category text" in SQL.split("create table mails", 1)[1].split(");", 1)[0]


def test_reserve_mail_also_locks_the_student():
    body = SQL.split("create function reserve_mail", 1)[1].split("$$;", 1)[0]
    student = body.index("pg_advisory_xact_lock(hashtext(p_student_id::text))")
    assert student < body.index("pg_advisory_xact_lock(hashtext(p_company_id))")


def test_the_pending_window_comes_from_the_server_too():
    body = SQL.split("create function reserve_mail", 1)[1].split("$$;", 1)[0]
    assert "interval '7 days'" not in body and "'presumed_sent_days'" in body
