"""A read-only query the owner runs after pasting migrations (D88)."""

from pathlib import Path

CHECK = Path(__file__).parents[1] / "supabase" / "check_migrations.sql"


def test_the_check_covers_every_student_migration_and_writes_nothing():
    sql = CHECK.read_text().lower()
    for name in ("m0004_profiles", "m0004_degree", "m0004_cv", "m0005_university",
                 "m0006_codes", "m0007_save", "m0007_redacted", "m0008_slots",
                 "m0009_roles", "m0010_student"):
        assert name in sql, name
    for word in ("insert ", "update ", "delete ", "drop ", "alter ", "create "):
        assert word not in sql, word
