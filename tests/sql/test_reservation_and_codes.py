"""Behaviour of reserve_mail and of the invitation codes on a real database."""

import threading
import uuid

import psycopg
import pytest

from tests.sql.conftest import as_role
from tests.sql.helpers import company, mail_row, reserve, student


def test_two_students_cannot_both_take_the_last_slot(database_uri):
    with psycopg.connect(database_uri, autocommit=True) as conn:
        cid = company(conn, cid=f"race-{uuid.uuid4().hex[:6]}")
        for _ in range(2):
            sid = student(conn)
            conn.execute("select reserve_mail(%s, %s, null, %s::jsonb)",
                         (sid, cid, mail_row(round_id=f"r-{cid}")))
        racers = [student(conn) for _ in range(6)]
    results, barrier = [], threading.Barrier(len(racers))

    def race(sid):
        with psycopg.connect(database_uri, autocommit=True) as conn:
            barrier.wait()
            results.append(conn.execute("select reserve_mail(%s, %s, null, %s::jsonb)",
                                        (sid, cid, mail_row(round_id=f"r-{cid}"))).fetchone()[0])
    threads = [threading.Thread(target=race, args=(s,)) for s in racers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in results if r["ok"]) == 1
    assert {r["reason"] for r in results if not r["ok"]} == {"company_full"}


def test_a_code_works_once(db):
    codes = [r[0] for r in db.execute("select * from create_invitation_codes(2)")]
    assert all(c.startswith("KS-") and len(c) == 15 for c in codes)
    assert db.execute("select invitation_code_ok(%s)", (codes[0].lower(),)).fetchone()[0]
    db.execute("insert into auth.users (email, raw_user_meta_data) values "
               "('a@example.com', jsonb_build_object('invitation_code', %s::text))", (codes[0],))
    assert not db.execute("select invitation_code_ok(%s)", (codes[0],)).fetchone()[0]
    db.execute("savepoint again")
    with pytest.raises(psycopg.errors.RaiseException):
        db.execute("insert into auth.users (email, raw_user_meta_data) values "
                   "('b@example.com', jsonb_build_object('invitation_code', %s::text))", (codes[0],))
    db.execute("rollback to savepoint again")
    assert db.execute("select count(*) from invitation_codes where code_hash = %s",
                      (codes[0],)).fetchone()[0] == 0          # only fingerprints are stored


@pytest.mark.parametrize("function", ["create_invitation_codes(1)", "invitation_code_ok('x')",
                                      "cancel_invitation_code('x')"])
def test_codes_are_for_the_owner_and_the_server_only(db, function):
    as_role(db, "anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute(f"select {function}")


def test_an_abandoned_mail_keeps_its_slot_even_never_copied(db):
    cid = company(db, cid=f"ab-{uuid.uuid4().hex[:6]}")
    first = reserve(db, student(db), cid, round_id=f"r-{cid}")
    for _ in range(2):
        assert reserve(db, student(db), cid, round_id=f"r-{cid}")["ok"]
    db.execute("update mails set status = 'abandoned', copied_at = null where id = %s",
               (first["id"],))
    assert reserve(db, student(db), cid, round_id=f"r-{cid}")["reason"] == "company_full"


def test_a_mail_to_an_address_the_student_gave_is_kept(db):
    """Honest addresses (2026-11-19, point 4): address type `student` (migration 0010)."""
    sid = student(db)
    cid = company(db, cid=f"own-{uuid.uuid4().hex[:6]}")
    result = reserve(db, sid, cid, person_key="k-ben", address="ben@own.example.ch",
                     address_type="student", person_name="Ben Probe",
                     person_choice="other_on_list", round_id=f"r-{cid}")
    assert result["ok"], result
