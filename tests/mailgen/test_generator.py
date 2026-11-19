import re

import pytest

from kaltstart.mailgen.generator import generate
from kaltstart.mailgen.models import Example, MissingData
from tests.mailgen.helpers import company, contact, round_, student

LINE = "I used your robot arm at a university lab and saw how hard calibration was."
INFORMAL = {"du", "dich", "dir", "dein", "deine", "deinem", "deinen", "deiner",
            "ihr", "euch", "euer", "eure", "eurem", "euren", "eurer", "hast", "habt"}
FORMAL = {"Sie", "Ihnen", "Ihre", "Ihrer", "Ihrem", "Ihren"}


def mail(**changes):
    args = dict(student=student(), company=company(), round=round_(), contact=contact(),
                style="direct", language="en", company_line=None, variant=0)
    args.update(changes)
    return generate(args.pop("student"), args.pop("company"), args.pop("round"),
                    args.pop("contact"), **args)


def words(text):
    return set(re.findall(r"[A-Za-zÄÖÜäöüé]+", text))


def test_direct_greets_the_confirmed_person_by_first_name():
    assert mail().body.startswith("Hi Anna!")


def test_direct_greets_the_team_without_a_person():
    assert mail(contact=contact(person_name=None)).body.startswith("Hi Example Robotics team!")


def test_formal_greetings():
    assert mail(style="formal").body.startswith("Dear Anna Muster,")
    assert mail(style="formal", language="de").body.startswith("Guten Tag Anna Muster,")
    assert mail(style="formal", contact=contact(person_name=None)).body.startswith(
        "Dear Example Robotics team,")


SHOWCASE = student().examples[0].text_en
LEAD_INS = {("direct", "en"): "A bit about me:", ("round", "en"): "What I bring:",
            ("formal", "en"): "One example of my work:", ("direct", "de"): "Kurz zu mir:",
            ("round", "de"): "Was ich mitbringe:", ("formal", "de"): "Ein Beispiel aus meiner Arbeit:"}


@pytest.mark.parametrize("style,language", LEAD_INS)
def test_the_showcase_sentence_is_the_core_with_its_lead_in(style, language):
    m = mail(style=style, language=language)
    example = student().examples[0]
    text = example.text_en if language == "en" else example.text_de
    assert f"{LEAD_INS[(style, language)]} {text}" in m.body
    assert not m.used_company_line


@pytest.mark.parametrize("style", ["direct", "round", "formal"])
def test_the_company_line_comes_after_the_showcase(style):
    m = mail(style=style, company_line=LINE)
    assert m.used_company_line
    paragraphs = m.body.split("\n\n")
    showcase = next(i for i, p in enumerate(paragraphs) if SHOWCASE in p)
    assert paragraphs[showcase + 1] == LINE


@pytest.mark.parametrize("style", ["round", "formal"])
def test_the_role_paragraph_gives_way_to_the_company_line(style):
    role = "New funding means ambitious targets."
    assert role in mail(style=style).body
    assert role not in mail(style=style, company_line=LINE).body


def test_the_chosen_example_is_used():
    two = student(examples=(Example("First example here.", "Erstes Beispiel."),
                            Example("Second example here.", "Zweites Beispiel.")),
                  chosen_example=1)
    assert "Second example here." in mail(student=two).body


@pytest.mark.parametrize("changes,field", [
    (dict(first_name=""), "first_name"), (dict(last_name=" "), "last_name"),
    (dict(programme=""), "programme"), (dict(start_date=None), "start_date"),
    (dict(duration_months=None), "duration_months"),
    (dict(request="part_time", duration_months=None, workload_percent=None), "workload_percent"),
])
def test_each_missing_field_is_named(changes, field):
    with pytest.raises(MissingData) as error:
        mail(student=student(**changes))
    assert error.value.fields == (field,)


def test_missing_address_is_named():
    with pytest.raises(MissingData) as error:
        mail(contact=contact(address=None))
    assert error.value.fields == ("contact_address",)


def test_a_mail_needs_a_showcase_sentence_in_its_language():
    english_only = student(examples=(Example("Only English.", None),))
    for line in (None, "Ich kenne euer Produkt."):
        with pytest.raises(MissingData) as error:
            mail(student=english_only, language="de", company_line=line)
        assert error.value.fields == ("example",)


def test_several_missing_fields_are_named_in_order():
    with pytest.raises(MissingData) as error:
        mail(student=student(first_name="", programme=""), contact=contact(address=None))
    assert error.value.fields == ("first_name", "programme", "contact_address")


def test_texts_over_200_characters_are_refused():
    with pytest.raises(ValueError):
        mail(company_line="x" * 201)


def test_unknown_style_or_language_is_refused():
    with pytest.raises(ValueError):
        mail(style="casual")
    with pytest.raises(ValueError):
        mail(language="fr")


@pytest.mark.parametrize("name", ["Fuchs & Eule", "O'Neil Labs"])
def test_company_names_appear_as_written(name):
    text = mail(company=company(name=name), contact=contact(person_name=None)).body
    assert name in text and "&amp;" not in text and "&#39;" not in text


@pytest.mark.parametrize("style", ["direct", "round"])
@pytest.mark.parametrize("person", ["Anna Muster", None])
def test_german_direct_and_round_use_du(style, person):
    text = mail(style=style, language="de", contact=contact(person_name=person)).body
    assert not FORMAL & words(text)


@pytest.mark.parametrize("person", ["Anna Muster", None])
def test_german_formal_uses_sie(person):
    text = mail(style="formal", language="de", contact=contact(person_name=person)).body
    assert not INFORMAL & words(text)          # case-sensitive: "Ihr" is formal
    assert FORMAL & words(text)


@pytest.mark.parametrize("style", ["direct", "round", "formal"])
def test_no_german_mail_contains_sharp_s(style):
    assert "ß" not in mail(style=style, language="de").body


def test_link_placement():
    assert "This is me: https://example.com/lea" in mail().body
    assert "https://example.com/lea" in mail(style="round").body.split("\n\n")[-1]
    assert "https://example.com/lea" in mail(style="formal").body.split("\n\n")[-1]
    for style in ("direct", "round", "formal"):
        assert "This is me" not in mail(style=style, student=student(link=None)).body
        assert "https://" not in mail(style=style, student=student(link=None)).body


def test_the_mail_names_the_round_and_never_a_lead():
    text = mail(style="round").body
    assert "€8M Series A" in text and "Example Ventures" in text and "led by" not in text


def test_variant_changes_the_opening_of_direct():
    openings = {mail(variant=v).body.split("\n\n")[1] for v in range(3)}
    assert len(openings) == 3


def test_subject_and_metadata():
    m = mail(language="de", style="round")
    assert m.subject == "Nach eurer Series A: Growth bei Example Robotics"
    assert (m.language, m.style) == ("de", "round")


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize("number", [0, 1, 2])
def test_the_round_opening_names_the_role_once(language, number):
    for role in ("growth", "product", "data", "operations", "business_development"):
        text = mail(style="round", language=language, variant=number,
                    student=student(role=role)).body.split("\n\n")[1]
        opening = text.split(". ")[0] + ". " + text.split(". ")[1]
        assert opening.lower().count("growth") + opening.lower().count("wachstum") <= 1, opening


@pytest.mark.parametrize("style", ["direct", "round"])
def test_technical_roles_read_right_inside_a_sentence(style):
    en = mail(style=style, student=student(role="software_ai")).body
    assert "software and AI" in en and "software & ai" not in en.lower().replace("software and ai", "")
    de = mail(style=style, language="de", student=student(role="rd_hardware")).body
    assert "Bereich Forschung & Entwicklung" in de


def test_round_keeps_the_role_paragraph_apart():
    paragraphs = mail(style="round").body.split("\n\n")
    assert paragraphs[2] == f"What I bring: {student().examples[0].text_en}"
    assert paragraphs[3].startswith("New funding means")


@pytest.mark.parametrize("style,greeting", [("direct", "Hallo zusammen!"), ("round", "Hallo zusammen,")])
def test_german_team_greeting(style, greeting):
    text = mail(style=style, language="de", contact=contact(person_name=None)).body
    assert text.startswith(greeting)


# Honest addresses (design 2026-11-19, point 2): a named person reached through a
# shared address. The team is greeted and asked to pass the mail on.
@pytest.mark.parametrize("style,language,greeting,forward", [
    ("direct", "en", "Hi Example Robotics team!",
     "Could you pass this on to Anna Muster (VP of Product)? Thank you!"),
    ("round", "en", "Hi Example Robotics team,",
     "Could you pass this on to Anna Muster (VP of Product)? Thank you!"),
    ("formal", "en", "Dear Example Robotics team,",
     "Could you please forward this message to Anna Muster, VP of Product? Thank you."),
    ("direct", "de", "Hallo zusammen!",
     "Könntet ihr das bitte an Anna Muster (VP of Product) weiterleiten? Danke!"),
    ("formal", "de", "Guten Tag,",
     "Könnten Sie diese Nachricht bitte an Anna Muster (VP of Product) weiterleiten? Vielen Dank."),
])
@pytest.mark.parametrize("address_type", ["generic", "careers"])
def test_a_shared_address_asks_the_team_to_pass_it_on(style, language, greeting, forward,
                                                      address_type):
    body = mail(style=style, language=language, contact=contact(
        address="info@example.de", address_type=address_type,
        person_title="VP of Product")).body
    paragraphs = body.split("\n\n")
    assert paragraphs[0] == greeting and paragraphs[1] == forward


def test_the_forward_line_without_a_title():
    body = mail(contact=contact(address="info@example.de", address_type="generic")).body
    assert body.split("\n\n")[1] == "Could you pass this on to Anna Muster? Thank you!"


@pytest.mark.parametrize("address_type", ["personal", "student"])
def test_the_persons_own_address_greets_them(address_type):
    body = mail(contact=contact(address_type=address_type, person_title="VP of Product")).body
    assert body.startswith("Hi Anna!") and "pass this on" not in body


def test_no_name_no_forward_line():
    body = mail(contact=contact(address="info@example.de", address_type="generic",
                                person_name=None)).body
    assert body.startswith("Hi Example Robotics team!") and "pass this on" not in body


def test_a_very_long_title_is_left_out_of_the_forward_line():
    title = "Senior Vice President Global Product Management Strategy and Customer Operations Europe"
    body = mail(contact=contact(address="info@example.de", address_type="generic",
                                person_title=title)).body
    assert body.split("\n\n")[1] == "Could you pass this on to Anna Muster? Thank you!"
