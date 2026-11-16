"""Inputs found by the final review of Phase 3 that broke or spoiled a mail."""

import pytest

from kaltstart.mailgen.generator import generate
from kaltstart.mailgen.models import Example, TooLong
from kaltstart.mailgen.phrases import amount, round_name
from tests.mailgen.helpers import company, contact, round_, student


def mail(**changes):
    args = dict(student=student(), company=company(), round=round_(), contact=contact(),
                style="direct", language="en", company_line=None, variant=0)
    args.update(changes)
    return generate(args.pop("student"), args.pop("company"), args.pop("round"),
                    args.pop("contact"), **args)


@pytest.mark.parametrize("line", [
    "None of the tools I tried handled calibration well.",
    "Have you thought about a mobile app ?",
    "My idea : a {simple} dashboard.",
])
def test_ordinary_student_text_never_crashes(line):
    for style in ("direct", "round", "formal"):
        assert line.rstrip(".") in mail(style=style, company_line=line).body


def test_a_blank_person_name_greets_the_team():
    assert mail(contact=contact(person_name="  ")).body.startswith("Hi Example Robotics team!")


@pytest.mark.parametrize("name,greeting", [("Dr. Anna Muster", "Hi Anna!"),
                                           ("Prof. Dr. Anna Muster", "Hi Anna!")])
def test_titles_are_skipped_in_the_first_name(name, greeting):
    assert mail(contact=contact(person_name=name)).body.startswith(greeting)


def test_a_student_text_over_35_words_is_refused_by_name():
    with pytest.raises(TooLong) as error:
        mail(company_line=" ".join(["word"] * 36))
    assert error.value.field == "company_line"


def test_long_names_and_programme_still_fit():
    long = student(first_name="Maria Luisa", last_name="van der Berg",
                   programme="Master of Arts in Strategy and International Management (SIM)")
    line = " ".join(["word"] * 35)
    for style in ("direct", "round", "formal"):
        for language in ("en", "de"):
            for number in (0, 1, 2):
                m = mail(student=long, style=style, language=language, company_line=line,
                         variant=number, company=company(name="Example Robotics And Autonomous X"),
                         round=round_(investors=("Example Ventures Growth Opportunities", "B")))
                assert len(m.body.split()) <= 150


def test_a_programme_over_70_characters_is_refused():
    with pytest.raises(TooLong) as error:
        mail(student=student(programme="x" * 71))
    assert error.value.field == "programme"


@pytest.mark.parametrize("value,en,de", [
    (40_000, "€40K", "40 Tsd. €"), (950_000, "€950K", "950 Tsd. €"), (999_700, "€1M", "1 Mio. €")])
def test_amounts_under_a_million(value, en, de):
    r = round_(amount_eur=value)
    assert amount(r, "en") == en and amount(r, "de") == de


@pytest.mark.parametrize("programme", ["International Affairs", "Economics", "Accounting and Finance"])
def test_no_article_error_before_a_programme(programme):
    body = mail(student=student(programme=programme), style="round").body
    assert f"a {programme}" not in body and f"an {programme}" not in body


@pytest.mark.parametrize("number", [0, 1, 2])
def test_german_roles_read_as_a_field(number):
    for style in ("direct", "round"):
        body = mail(student=student(role="product"), style=style, language="de", variant=number).body
        for wrong in ("bei Produkt", "und Produkt", "meist, Produkt"):
            assert wrong not in body
        assert "Bereich Produkt" in body


def test_english_round_names_the_team_not_a_bare_role():
    body = mail(student=student(role="data"), style="round", variant=2).body
    assert "building out data," not in body and "the data team" in body


def test_an_investor_ending_in_a_period_gives_no_double_period():
    r = round_(investors=("Example Holdings Inc.",))
    for style in ("direct", "round", "formal"):
        for number in (0, 1, 2):
            assert ".." not in mail(round=r, style=style, variant=number).body


def test_seed_rounds_read_naturally():
    assert round_name("Seed", "en") == "seed round" and round_name("Seed", "de") == "Seed-Runde"
    assert round_name("Pre-Seed", "en") == "pre-seed round"
    assert round_name("Pre-Seed", "de") == "Pre-Seed-Runde"


def test_german_compound_subject_is_hyphenated():
    m = mail(student=student(role="business_development"), style="formal", language="de",
             company=company(name="Example"))
    assert "Business-Development-Praktikum" in m.subject


@pytest.mark.parametrize("changes", [dict(variant=3), dict(variant=-1)])
def test_an_out_of_range_variant_is_refused(changes):
    with pytest.raises(ValueError):
        mail(**changes)


@pytest.mark.parametrize("changes", [dict(role="design"), dict(request="freelance")])
def test_an_unknown_role_or_request_is_refused(changes):
    with pytest.raises(ValueError):
        mail(student=student(**changes))


def test_the_two_sentences_together_stay_within_50_words():
    showcase = " ".join(["word"] * 30) + "."
    two = student(examples=(Example(showcase, showcase),))
    assert mail(student=two, company_line=" ".join(["line"] * 20))
    with pytest.raises(TooLong) as error:
        mail(student=two, company_line=" ".join(["line"] * 21))
    assert error.value.field == "company_line"
