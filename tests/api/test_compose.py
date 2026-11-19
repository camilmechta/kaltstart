from datetime import date

import pytest

from kaltstart.api.compose import NoAddress, Recipient, choose, suggested, to_mailgen
from kaltstart.api.store import EmailRow, PersonRow, Profile, Showcase
from kaltstart.contacts.exclusions import person_key
from tests.api.test_store import company

ANNA = PersonRow("Anna Muster", "Head of Growth", ("growth",), "head",
                 "https://c1.example.ch/team", date(2026, 11, 15))
BEN = PersonRow("Ben Probe", "CTO", ("leadership",), "head", "https://c1.example.ch/team",
                date(2026, 11, 15))
EMAILS = [EmailRow("anna.muster@c1.example.ch", "personal", "https://c1.example.ch/team"),
          EmailRow("jobs@c1.example.ch", "careers", "https://c1.example.ch/jobs"),
          EmailRow("info@c1.example.ch", "generic", "https://c1.example.ch/imprint")]
PROFILE = Profile(id="s1", first_name="Lea", last_name="Beispiel", programme="Business Innovation",
                  languages=("en",), target_role="growth", request="internship",
                  start_date=date(2027, 4, 1), duration_months=3)
C1 = company(1, size="medium")


def test_the_suggested_person_follows_the_target_role():
    assert suggested(C1, [BEN, ANNA], PROFILE).name == "Anna Muster"
    ops = Profile(**{**PROFILE.__dict__, "target_role": "operations"})
    assert suggested(C1, [BEN], ops) is None          # medium company, no recruiter, no ops


def test_choosing_the_suggested_person_uses_their_own_address():
    r = choose(C1, [BEN, ANNA], EMAILS, PROFILE, "suggested")
    assert r == Recipient("Anna Muster", "https://c1.example.ch/team",
                          "anna.muster@c1.example.ch", "personal", "suggested",
                          person_key("c1", "Anna Muster"), "Head of Growth")


def test_someone_else_on_the_list_gets_the_careers_address():
    r = choose(C1, [BEN, ANNA], EMAILS, PROFILE, "other_on_list", person_index=0)
    assert (r.person_name, r.address, r.person_choice) == ("Ben Probe", "jobs@c1.example.ch", "other_on_list")


@pytest.mark.parametrize("index", [-1, 2, None])
def test_an_index_outside_the_list_is_refused(index):
    with pytest.raises(ValueError):
        choose(C1, [BEN, ANNA], EMAILS, PROFILE, "other_on_list", person_index=index)


def test_a_typed_name_never_gets_a_personal_address():
    r = choose(C1, [ANNA], EMAILS, PROFILE, "typed", typed_name="  Clara   Vorlage ")
    assert (r.person_name, r.address, r.person_source_url) == ("Clara Vorlage", "jobs@c1.example.ch", None)
    with pytest.raises(ValueError):
        choose(C1, [ANNA], EMAILS, PROFILE, "typed", typed_name="")


def test_the_team_gets_the_careers_then_the_general_address():
    assert choose(C1, [ANNA], EMAILS, PROFILE, "team").address == "jobs@c1.example.ch"
    general = [e for e in EMAILS if e.type == "generic"]
    r = choose(C1, [ANNA], general, PROFILE, "team")
    assert (r.address, r.person_name, r.person_key) == ("info@c1.example.ch", None, None)


def test_no_usable_address_is_said_plainly():
    with pytest.raises(NoAddress):
        choose(C1, [ANNA], [EMAILS[0]], PROFILE, "team")


def test_an_unknown_choice_is_refused():
    with pytest.raises(ValueError):
        choose(C1, [ANNA], EMAILS, PROFILE, "anyone")


def test_to_mailgen_builds_the_generator_inputs():
    showcases = [Showcase(1, "First.", None), Showcase(2, "Second.", "Zweite.")]
    recipient = choose(C1, [ANNA], EMAILS, PROFILE, "suggested")
    student, comp, rnd, contact = to_mailgen(PROFILE, showcases, C1, recipient, chosen_showcase=2)
    assert (student.first_name, student.role, student.chosen_example) == ("Lea", "growth", 1)
    assert [e.text_en for e in student.examples] == ["First.", "Second."]
    assert (comp.name, comp.country) == (C1.name, "Switzerland")
    assert (rnd.stage, rnd.size_category) == ("Seed", "medium")
    assert (contact.address, contact.person_name) == ("anna.muster@c1.example.ch", "Anna Muster")


def test_why_a_person_is_suggested():
    from kaltstart.api.compose import why
    assert why(ANNA, PROFILE, C1) == "Their title, Head of Growth, matches your target role: Growth."
    founder = PersonRow("Ben Probe", "Co-Founder & CEO", ("leadership",), "head", "u", date(2026, 11, 15))
    small = company(1, size="small")
    ops = Profile(**{**PROFILE.__dict__, "target_role": "operations"})
    assert why(founder, ops, small) == ("At a small company, the founders and the leadership "
                                        "read applications themselves.")
    recruiter = PersonRow("Noah Entwurf", "Talent Acquisition Manager", ("recruiting",), "manager",
                          "u", date(2026, 11, 15))
    assert why(recruiter, ops, company(1, size="large")) == (
        "At a company this size, the recruiting team handles applications.")


# Technical roles (technical roles design, sections 6 and 9).
FOUNDER = PersonRow("Ben Probe", "Co-Founder & CEO", ("leadership",), "head",
                    "https://c1.example.ch/team", date(2026, 11, 15))
CTO = PersonRow("Jonas Beispiel", "CTO", ("leadership",), "head",
                "https://c1.example.ch/team", date(2026, 11, 15))
HEAD_ENG = PersonRow("Tim Muster", "Head of Engineering", ("engineering",), "head",
                     "https://c1.example.ch/team", date(2026, 11, 15))


def with_role(role):
    return Profile(**{**PROFILE.__dict__, "target_role": role})


def test_a_technical_role_is_offered_the_cto_at_a_small_company():
    from kaltstart.api.compose import why
    small = company(1, size="small")
    assert suggested(small, [FOUNDER, CTO], with_role("rd_hardware")).name == "Jonas Beispiel"
    assert why(CTO, with_role("rd_hardware"), small) == (
        "At a small company, the CTO reads applications for technical roles.")


def test_a_technical_head_matches_the_technical_role():
    from kaltstart.api.compose import why
    assert suggested(C1, [CTO, HEAD_ENG], with_role("software_ai")).name == "Tim Muster"
    assert why(HEAD_ENG, with_role("software_ai"), C1) == (
        "Their title, Head of Engineering, matches your target role: Software & AI.")


# Honest addresses (design 2026-11-19, point 4): an address the student gives.
def test_the_students_address_is_used_for_a_named_person():
    r = choose(C1, [BEN, ANNA], EMAILS, PROFILE, "other_on_list", person_index=0,
               their_address=" ben@c1.example.ch ")
    assert (r.person_name, r.address, r.address_type) == ("Ben Probe", "ben@c1.example.ch", "student")
    assert r.person_title == "CTO"


def test_the_students_address_with_a_typed_name():
    r = choose(C1, [BEN, ANNA], EMAILS, PROFILE, "typed", typed_name="Mia Muster",
               their_address="mia@c1.example.ch")
    assert (r.address, r.address_type, r.person_title) == ("mia@c1.example.ch", "student", None)


def test_the_students_address_is_ignored_without_a_name():
    r = choose(C1, [BEN, ANNA], EMAILS, PROFILE, "team", their_address="mia@c1.example.ch")
    assert r.address_type in ("careers", "generic") and r.address != "mia@c1.example.ch"


@pytest.mark.parametrize("bad", ["ben", "ben@", "@c1.example.ch", "ben@c1", "ben @c1.example.ch",
                                 "a@b@c1.example.ch", "x" * 250 + "@c1.example.ch"])
def test_a_wrong_student_address_is_refused(bad):
    from kaltstart.api.compose import BadAddress
    with pytest.raises(BadAddress):
        choose(C1, [BEN, ANNA], EMAILS, PROFILE, "other_on_list", person_index=0, their_address=bad)


def test_a_shared_address_carries_the_title_to_the_mail():
    r = choose(C1, [BEN, ANNA], EMAILS, PROFILE, "other_on_list", person_index=0)
    assert r.address_type == "careers" and r.person_title == "CTO"
    contact = to_mailgen(PROFILE, [Showcase(1, "I did a thing that matters.", None)], C1, r)[3]
    assert contact.person_title == "CTO"
