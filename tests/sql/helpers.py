"""Invented rows for the SQL tests."""

import json
import uuid

LIMITS = {"company_cap": 3, "cap_days": 30, "round_cap": {"small": 6, "medium": 9, "large": 15},
          "speed": 10, "speed_days": 7, "pending": 5, "presumed_sent_days": 7}


def student(db, code_ok=False):
    sid = uuid.uuid4()
    db.execute("alter table auth.users disable trigger check_invitation_code")
    db.execute("insert into auth.users (id, email) values (%s, %s)", (sid, f"{sid}@example.com"))
    db.execute("alter table auth.users enable trigger check_invitation_code")
    return sid


def company(db, cid="c1", name="Example Robotics"):
    db.execute("insert into companies (id, name, country, techeu_url) values (%s, %s, 'Switzerland', "
               "'https://example.com/c') on conflict do nothing", (cid, name))
    db.execute("insert into rounds (id, company_id, date, size_category, source_url) values "
               "(%s, %s, current_date, 'small', 'https://example.com/r') on conflict do nothing",
               (f"r-{cid}", cid))
    return cid


def mail_row(**changes):
    row = {"round_id": "r-c1", "address": "info@c1.example.ch", "address_type": "generic",
           "person_name": None, "person_choice": "team", "person_source_url": None,
           "style": "direct", "language": "en", "company_line": None,
           "used_company_line": False, "subject": "Example internship?",
           "body": "Hi Example team!", "variant": 0, "size_category": "small",
           "limits": LIMITS}
    row.update(changes)
    return json.dumps(row)


def reserve(db, sid, cid="c1", person_key=None, **changes):
    return db.execute("select reserve_mail(%s, %s, %s, %s::jsonb)",
                      (sid, cid, person_key, mail_row(**changes))).fetchone()[0]
