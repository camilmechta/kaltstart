import pytest

from kaltstart.mailgen.language import choose_language
from tests.mailgen.helpers import company, student


@pytest.mark.parametrize("country", ["Germany", "Austria"])
def test_a_german_speaker_writes_in_german_to_germany_and_austria(country):
    assert choose_language(student(), company(country=country)) == "de"


@pytest.mark.parametrize("region,expected", [("Zurich", "de"), ("Bern", "de"), ("Vaud", "en")])
def test_swiss_region_decides(region, expected):
    swiss = company(country="Switzerland", region=region, city=None)
    assert choose_language(student(), swiss) == expected


@pytest.mark.parametrize("city,expected", [("Basel", "de"), ("Geneva", "en"), (None, "en")])
def test_swiss_city_decides_without_a_region(city, expected):
    swiss = company(country="Switzerland", region=None, city=city)
    assert choose_language(student(), swiss) == expected


def test_a_student_without_german_writes_in_english():
    assert choose_language(student(languages=("en", "fr")), company(country="Germany")) == "en"
