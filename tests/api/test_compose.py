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
                          person_key("c1", "Anna Muster"))


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
