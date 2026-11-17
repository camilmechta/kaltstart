"""Problem 2: a removal on request also clears kept mails (D87)."""

import pytest
import psycopg

from tests.sql.conftest import as_role
from tests.sql.helpers import company, reserve, student


def key(db, cid, name):
    return db.execute("select contact_person_key(%s, %s)", (cid, name)).fetchone()[0]


def mail(db, mail_id):
    return db.execute("select address, subject, body, person_name, person_source_url, "
                      "company_line, redacted_at is not null, status, person_key "
                      "from mails where id = %s", (mail_id,)).fetchone()


def setup(db):
    company(db)
    db.execute("insert into contact_people (company_id, name, title, level, source_url, read_at) "
               "values ('c1', 'Anna Muster', 'Head of Growth', 'head', 'https://c1.example.ch/team', now()), "
               "('c1', 'Ben Probe', 'CTO', 'head', 'https://c1.example.ch/team', now())")
    anna = reserve(db, student(db), person_key=key(db, "c1", "Anna Muster"),
                   person_name="Anna Muster", person_choice="suggested",
                   address="anna.muster@c1.example.ch", address_type="personal",
                   person_source_url="https://c1.example.ch/team",
                   body="Hi Anna!\n\nA mail.", subject="Example internship?")
    ben = reserve(db, student(db), person_key=key(db, "c1", "Ben Probe"),
                  person_name="Ben Probe", person_choice="other_on_list",
                  address="ben.probe@c1.example.ch", address_type="personal",
                  body="Hi Ben!\n\nA mail.")
    return anna["id"], ben["id"]


def test_removing_a_person_clears_their_kept_mails_only(db):
    anna, ben = setup(db)
    db.execute("select exclude_person('c1', 'Anna Muster')")
    address, subject, body, name, source, line, redacted, status, person_key = mail(db, anna)
    assert (address, subject, body, name, source, line) == (None, None, None, None, None, None)
    assert redacted and status == "generated" and person_key   # kept for the caps and rules
    assert mail(db, ben)[:4] == ("ben.probe@c1.example.ch", "Example internship?",
                                 "Hi Ben!\n\nA mail.", "Ben Probe")
    assert not mail(db, ben)[6]


def test_removing_a_company_clears_all_its_kept_mails(db):
    anna, ben = setup(db)
    db.execute("select exclude_company('c1')")
    for mail_id in (anna, ben):
        assert mail(db, mail_id)[:6] == (None,) * 6 and mail(db, mail_id)[6]


def test_removals_can_be_run_again_without_error(db):
    anna, _ = setup(db)
    db.execute("select exclude_person('c1', 'Anna Muster')")
    first = db.execute("select redacted_at from mails where id = %s", (anna,)).fetchone()[0]
    db.execute("select exclude_person('c1', 'Anna Muster')")
    db.execute("select exclude_company('c1')")
    db.execute("select exclude_company('c1')")
    assert db.execute("select redacted_at from mails where id = %s", (anna,)).fetchone()[0] == first


def test_a_removed_person_is_not_collected_again(db):
    setup(db)
    db.execute("select exclude_person('c1', 'Anna Muster')")
    excluded = db.execute("select count(*) from contact_exclusions where company_id = 'c1' "
                          "and person_key = %s", (key(db, "c1", "Anna Muster"),)).fetchone()[0]
    assert excluded == 1
    assert db.execute("select count(*) from contact_people where name = 'Anna Muster'").fetchone()[0] == 0


def test_a_cleared_mail_still_counts_for_the_caps(db):
    company(db)
    for _ in range(3):
        reserve(db, student(db))
    db.execute("select exclude_company('c1')")
    assert reserve(db, student(db))["reason"] == "company_full"


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_only_the_owner_may_remove(db, role):
    setup(db)
    as_role(db, role)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("select exclude_company('c1')")
