"""Every combination of spec section 10, with every input at its longest."""

import itertools
import re

import pytest

from kaltstart.mailgen.generator import MAX_BODY_WORDS, generate
from kaltstart.mailgen.models import LANGUAGES, REQUESTS, ROLES, STYLES, Example
from tests.mailgen.helpers import company, contact, round_, student

# The longest texts a student may write: a 60-word showcase sentence and a
# 35-word sentence about the company.
LONG_TEXT = " ".join(["abcd"] * 60)[:-1] + "."
LONG_LINE = " ".join(["abcd"] * 35)[:-1] + "."
LONG_COMPANY = "Example Robotics And Autonomous Systems X"          # 41 characters
LONG_INVESTOR = "Example Ventures Growth Opportunities Fund"[:40]
# The longest HSG programme name, and long first and last names.
LONG_PROGRAMME = "Master of Arts in Strategy and International Management (SIM)"
STAGES = ("Series A", "Seed", "Grant", "Other")
MISSING = {"none": {}, "no_amount": dict(amount_eur=None, amount_native=None),
           "no_investor": dict(investors=()),
           "neither": dict(amount_eur=None, amount_native=None, investors=())}
GAPS = re.compile(r"[{}]|\bNone\b|  | [.,!?:]|\n\n\n|led by|angeführt")


def cases(style):
    variants = (0, 1, 2, 3, 4, 5)       # every wording of every axis, both orders
    return itertools.product(("small", "medium", "large"), ROLES, REQUESTS, MISSING,
                             (True, False), variants, ("Prof. Dr. Anna Maria Muster", None))


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_combination(style, language):
    count = 0
    for size, role, kind, missing, with_line, number, person in cases(style):
        stu = student(role=role, request=kind, programme=LONG_PROGRAMME,
                      first_name="Maria Luisa", last_name="van der Berg-Muster", level="master",
                      duration_months=6 if kind == "internship" else None,
                      workload_percent=40 if kind == "part_time" else None,
                      link="https://example.com/" + "x" * 20,
                      examples=(Example(LONG_TEXT, LONG_TEXT),))
        values = dict(size_category=size, investors=(LONG_INVESTOR, "Other Capital"),
                      stage=STAGES[(ROLES.index(role) + number) % len(STAGES)])
        values.update(MISSING[missing])
        rnd = round_(**values)
        m = generate(stu, company(name=LONG_COMPANY), rnd, contact(person_name=person),
                     style=style, language=language,
                     company_line=LONG_LINE if with_line else None, variant=number)
        case = (style, language, size, role, kind, missing, with_line, number, person)
        assert not GAPS.search(m.body), (case, m.body)
        assert len(m.body.split()) <= MAX_BODY_WORDS, (case, len(m.body.split()))
        assert 0 < len(m.subject) <= 60, (case, m.subject)
        assert m.used_company_line is with_line
        if language == "de":
            assert "ß" not in m.body + m.subject, case
        count += 1
    assert count == 2880   # 3 sizes x 5 roles x 2 requests x 4 missing x 2 lines x 6 variants x 2 persons
