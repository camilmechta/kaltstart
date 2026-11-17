"""One full mail per style and language, read by the owner: any change of
text shows here. To accept a deliberate change, regenerate with
`python -m tests.mailgen.test_golden` and read the diff."""

from pathlib import Path

import pytest

from kaltstart.mailgen.generator import generate
from kaltstart.mailgen.models import LANGUAGES, STYLES
from tests.mailgen.helpers import company, contact, round_, student

GOLDEN = Path(__file__).parent / "golden"
LINE = {"en": "I tried your robot arm at a university lab and saw how much time calibration takes.",
        "de": "Ich habe euren Roboterarm in einem Uni-Labor genutzt und gesehen, wie lange die Kalibrierung dauert."}


FORMAL_DE = "Ich habe Ihren Roboterarm in einem Uni-Labor genutzt und gesehen, wie lange die Kalibrierung dauert."
# k = 0 with and without a company line; k = 1 and 2 (the second and third
# mail to one company) without, to read how the wordings vary.
CASES = [(style, language, with_line, 0) for style in STYLES for language in LANGUAGES
         for with_line in (True, False)] + \
        [(style, language, False, k) for style in STYLES for language in LANGUAGES
         for k in (1, 2, 3)]


def name(style: str, language: str, with_line: bool, k: int = 0) -> str:
    return (f"{style}_{language}{'_with_company_line' if with_line else ''}"
            f"{f'_v{k}' if k else ''}.txt")


def render(style: str, language: str, with_line: bool, k: int = 0) -> str:
    person = None if style == "formal" else "Anna Muster"
    line = FORMAL_DE if (style, language) == ("formal", "de") else LINE[language]
    m = generate(student(), company(), round_(), contact(person_name=person), style=style,
                 language=language, company_line=line if with_line else None, variant=k)
    return f"Subject: {m.subject}\n\n{m.body}\n"


@pytest.mark.parametrize("style,language,with_line,k", CASES)
def test_golden_mail(style, language, with_line, k):
    expected = (GOLDEN / name(style, language, with_line, k)).read_text(encoding="utf-8")
    assert render(style, language, with_line, k) == expected


if __name__ == "__main__":
    for path in GOLDEN.glob("*.txt"):
        path.unlink()
    for case in CASES:
        (GOLDEN / name(*case)).write_text(render(*case), encoding="utf-8")
