"""Mails to one company differ (spec 2026-11-16-sending-limits-and-variation, 4)."""

import pytest

from kaltstart.mailgen.choices import axes
from kaltstart.mailgen.generator import generate
from kaltstart.mailgen.models import LANGUAGES, STYLES
from tests.mailgen.helpers import company, contact, round_, student

SHOWCASE = "I grew our newsletter to 4000 readers."


def mail(style, language, k, person="Anna Muster"):
    from kaltstart.mailgen.models import Example
    stu = student(examples=(Example(SHOWCASE, "Ich habe unseren Newsletter auf 4000 Leser gebracht."),))
    return generate(stu, company(), round_(), contact(person_name=person), style=style,
                    language=language, variant=k)


def test_axes_of_the_first_three_differ_everywhere():
    for k in range(3):
        assert axes(k)[:4] == (k, k, k, k)


def test_the_first_fifteen_combinations_are_distinct():
    assert len({axes(k)[:4] for k in range(15)}) == 15


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_three_mails_to_one_company_differ(style, language):
    mails = [mail(style, language, k) for k in range(3)]
    assert len({m.subject for m in mails}) == 3
    assert len({m.body for m in mails}) == 3
    lines = [m.body.split("\n\n")[2] for m in mails]          # the showcase paragraph
    lead_ins = {line.split(":", 1)[0] for line in lines}
    assert len(lead_ins) == 3, lines
    def close(body):
        paragraphs = [p for p in body.split("\n\n") if not ("http" in p and "\n" not in p)]
        return paragraphs[-2]                     # the last one is the signature
    assert len({close(m.body) for m in mails}) == 3


@pytest.mark.parametrize("style", STYLES)
def test_order_moves_the_intro_after_the_showcase(style):
    first, moved = mail(style, "en", 0).body, mail(style, "en", 3).body
    assert first.index("HSG") < first.index(SHOWCASE)
    assert moved.index(SHOWCASE) < moved.index("HSG")


def test_a_negative_variant_is_refused():
    with pytest.raises(ValueError):
        mail("direct", "en", -1)



def test_reviewed_wordings():
    formal_de = mail("formal", "de", 1, person=None).body
    assert "Die Nachricht hat meine Aufmerksamkeit geweckt." in formal_de
    assert "Über die Gelegenheit zu einem kurzen Gespräch würde ich mich freuen." in formal_de
    assert "The news caught my attention." in mail("formal", "en", 1, person=None).body
    assert "Wäre das für dich interessant?" in mail("direct", "de", 1).body
    assert "Wäre das für euch interessant?" in mail("direct", "de", 1, person=None).body


def test_the_degree_level_is_said_in_the_mail():
    from kaltstart.mailgen.models import Example
    base = dict(examples=(Example(SHOWCASE, "Ich habe unseren Newsletter auf 4000 Leser gebracht."),),
                level="master")
    en = generate(student(**base), company(), round_(), contact(person_name="Anna Muster"),
                  style="direct", language="en", variant=0).body
    assert "I'm doing a Master in Business Innovation at HSG and am looking for" in en
    assert en.rstrip().endswith("Master in Business Innovation, HSG\nhttps://example.com/lea") \
        or "Master in Business Innovation, HSG" in en
    formal = generate(student(**base), company(), round_(), contact(), style="formal",
                      language="en", variant=0).body
    assert "I am completing a Master in Business Innovation at the University of St. Gallen (HSG)" in formal
    de = generate(student(**{**base, "level": "bachelor"}), company(), round_(),
                  contact(person_name="Anna Muster"), style="direct", language="de", variant=0).body
    assert "Ich mache einen Bachelor in Business Innovation an der HSG und suche" in de
