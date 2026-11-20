def test_every_migration_applies_on_postgres(db):
    tables = {r[0] for r in db.execute(
        "select table_name from information_schema.tables where table_schema = 'public'")}
    for table in ("companies", "rounds", "contact_people", "profiles", "mails", "invitation_codes"):
        assert table in tables, table


def test_a_mail_can_be_marked_no_reply(db):
    from tests.sql.helpers import company, reserve, student
    sid = student(db)
    company(db)
    result = reserve(db, sid)
    mail_id = result["id"]
    db.execute("update mails set status = 'sent', sent_at = now() where id = %s", (mail_id,))
    db.execute("update mails set status = 'no_reply', no_reply_at = now() where id = %s",
               (mail_id,))
    assert db.execute("select status from mails where id = %s", (mail_id,)).fetchone()[0] \
        == "no_reply"
