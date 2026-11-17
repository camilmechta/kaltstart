def test_every_migration_applies_on_postgres(db):
    tables = {r[0] for r in db.execute(
        "select table_name from information_schema.tables where table_schema = 'public'")}
    for table in ("companies", "rounds", "contact_people", "profiles", "mails", "invitation_codes"):
        assert table in tables, table
