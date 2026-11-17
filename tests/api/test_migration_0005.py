"""Migration 0005 adds the university to profiles (D85); 0004 is already applied."""

from pathlib import Path

SQL = (Path(__file__).parents[2] / "supabase" / "migrations" / "0005_university.sql")


def test_profiles_gain_a_university():
    sql = SQL.read_text()
    assert "alter table profiles add column if not exists university text not null default '';" in sql
    assert "drop" not in sql.lower() and "delete" not in sql.lower()
