from pathlib import Path


def test_the_check_is_all_true_once_every_migration_is_applied(db):
    sql = (Path(__file__).parents[2] / "supabase" / "check_migrations.sql").read_text()
    row = db.execute(sql).fetchone()
    assert all(row), row
