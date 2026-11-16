"""Every combination of spec section 10, with every input at its longest."""

import itertools
import re

import pytest

from kaltstart.mailgen.generator import MAX_BODY_WORDS, generate
from kaltstart.mailgen.models import LANGUAGES, REQUESTS, ROLES, STYLES, Example
from tests.mailgen.helpers import company, contact, round_, student

# 200 characters of three-letter words: the most words a student text can hold
# with ordinary words (50).
LONG_TEXT = " ".join(["abc"] * 50)[:199] + "."
LONG_COMPANY = "Example Robotics And Autonomous Systems X"          # 41 characters
LONG_INVESTOR = "Example Ventures Growth Opportunities Fund"[:40]
LONG_PROGRAMME = "Master in Banking and Finance (MBF)"
MISSING = {"none": {}, "no_amount": dict(amount_eur=None, amount_native=None),
           "no_investor": dict(investors=()),
           "neither": dict(amount_eur=None, amount_native=None, investors=())}
GAPS = re.compile(r"[{}]|\bNone\b|  | [.,!?:]|\n\n\n|led by|angeführt")


def cases(style):
    variants = (0,) if style == "formal" else (0, 1, 2)
    return itertools.product(("small", "medium", "large"), ROLES, REQUESTS, MISSING,
                             (True, False), variants, ("Anna Muster", None))


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_combination(style, language):
    count = 0
    for size, role, kind, missing, with_line, number, person in cases(style):
        stu = student(role=role, request=kind, programme=LONG_PROGRAMME,
                      duration_months=6 if kind == "internship" else None,
                      workload_percent=40 if kind == "part_time" else None,
                      link="https://example.com/" + "x" * 20,
                      examples=(Example(LONG_TEXT, LONG_TEXT),))
        values = dict(size_category=size, investors=(LONG_INVESTOR, "Other Capital"))
        values.update(MISSING[missing])
        rnd = round_(**values)
        m = generate(stu, company(name=LONG_COMPANY), rnd, contact(person_name=person),
                     style=style, language=language,
                     company_line=LONG_TEXT if with_line else None, variant=number)
        case = (style, language, size, role, kind, missing, with_line, number, person)
        assert not GAPS.search(m.body), (case, m.body)
        assert len(m.body.split()) <= MAX_BODY_WORDS, (case, len(m.body.split()))
        assert 0 < len(m.subject) <= 60, (case, m.subject)
        assert m.used_company_line is with_line
        if language == "de":
            assert "ß" not in m.body + m.subject, case
        count += 1
    assert count == (480 if style == "formal" else 1440)   # person greeted or not included
