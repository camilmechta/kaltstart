"""Migration 0011 accepts LinkedIn messages (design 2026-11-19)."""

from pathlib import Path

SQL = Path(__file__).parents[2] / "supabase" / "migrations" / "0011_linkedin.sql"


def test_the_address_type_check_accepts_linkedin():
    sql = SQL.read_text()
    assert "alter table mails drop constraint if exists mails_address_type_check;" in sql
    assert "('personal', 'careers', 'generic', 'student', 'linkedin')" in sql


def test_it_changes_no_data():
    sql = SQL.read_text().lower()
    for word in ("delete ", "update ", "drop table", "insert "):
        assert word not in sql, word
