"""Problem 1: the profile and its showcase sentences are saved in one transaction."""

import json

import psycopg
import pytest

from tests.sql.conftest import as_role
from tests.sql.helpers import student

PROFILE = {"first_name": "Lea", "last_name": "Beispiel", "programme": "Business Innovation",
           "university": "HSG", "degree_level": "master", "attach_cv": True,
           "languages": ["en"], "target_role": "growth", "request": "internship",
           "start_date": "2027-04-01", "duration_months": 3, "workload_percent": None,
           "link": None, "preferred_countries": [], "preferred_sectors": []}


def save(db, sid, profile, showcases):
    db.execute("select save_profile_and_showcases(%s, %s::jsonb, %s::jsonb)",
               (sid, json.dumps(profile), json.dumps(showcases)))


def showcases(db, sid):
    return db.execute("select position, text_en from showcases where student_id = %s "
                      "order by position", (sid,)).fetchall()


def test_profile_and_showcases_are_saved_together(db):
    sid = student(db)
    save(db, sid, PROFILE, [{"position": 1, "text_en": "One.", "text_de": None},
                            {"position": 2, "text_en": "Two.", "text_de": None}])
    assert db.execute("select first_name from profiles where id = %s", (sid,)).fetchone()[0] == "Lea"
    assert showcases(db, sid) == [(1, "One."), (2, "Two.")]


def test_removing_a_showcase_on_purpose_still_works(db):
    sid = student(db)
    save(db, sid, PROFILE, [{"position": 1, "text_en": "One.", "text_de": None},
                            {"position": 2, "text_en": "Two.", "text_de": None}])
    save(db, sid, PROFILE, [{"position": 1, "text_en": "One again.", "text_de": None}])
    assert showcases(db, sid) == [(1, "One again.")]


def test_a_failure_after_the_writes_began_keeps_everything(db):
    sid = student(db)
    save(db, sid, PROFILE, [{"position": 1, "text_en": "One.", "text_de": None}])
    db.execute("savepoint before")
    changed = dict(PROFILE, first_name="Changed")
    with pytest.raises(psycopg.errors.CheckViolation):
        # The profile is written first, then position 3 breaks the showcase check.
        save(db, sid, changed, [{"position": 3, "text_en": "Bad.", "text_de": None}])
    db.execute("rollback to savepoint before")
    assert db.execute("select first_name from profiles where id = %s", (sid,)).fetchone()[0] == "Lea"
    assert showcases(db, sid) == [(1, "One.")]


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_only_the_server_may_save(db, role):
    sid = student(db)
    as_role(db, role)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        save(db, sid, PROFILE, [])


def test_the_server_role_may_save(db):
    sid = student(db)
    as_role(db, "service_role")
    save(db, sid, PROFILE, [])


@pytest.mark.parametrize("role", ["software_ai", "rd_hardware"])
def test_a_technical_role_is_saved(db, role):
    sid = student(db)
    save(db, sid, dict(PROFILE, target_role=role), [])
    assert db.execute("select target_role from profiles where id = %s", (sid,)).fetchone()[0] == role


def test_an_unknown_role_is_refused(db):
    sid = student(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        save(db, sid, dict(PROFILE, target_role="engineering"), [])
