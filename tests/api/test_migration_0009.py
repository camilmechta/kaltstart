"""Migration 0009 accepts the two technical roles in profiles (technical roles design, section 7)."""

import re
from pathlib import Path

from kaltstart.mailgen.models import ROLES

SQL = Path(__file__).parents[2] / "supabase" / "migrations" / "0009_technical_roles.sql"


def test_the_role_check_is_replaced_with_the_seven_roles():
    sql = SQL.read_text()
    assert "alter table profiles drop constraint if exists profiles_target_role_check;" in sql
    check = sql[sql.index("add constraint profiles_target_role_check"):]
    assert tuple(re.findall(r"'([a-z_]+)'", check)) == ROLES


def test_it_changes_no_data():
    sql = SQL.read_text().lower()
    for word in ("delete ", "update ", "drop table", "insert "):
        assert word not in sql, word
