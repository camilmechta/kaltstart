import subprocess
import sys

import pytest

from kaltstart.mailgen.choices import subject, suggested_style, variant
from kaltstart.mailgen.models import LANGUAGES, REQUESTS, ROLES, STYLES
from kaltstart.mailgen.phrases import role_name
from tests.mailgen.helpers import contact, round_

PINNED = int(__import__("hashlib").sha256(b"s1\nc1").hexdigest()[:8], 16) % 3


def test_variant_is_pinned_and_stable_across_processes():
    assert variant("s1", "c1") == PINNED
    code = "from kaltstart.mailgen.choices import variant; print(variant('s1', 'c1'))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert int(out.stdout) == PINNED


def test_variants_differ_between_students():
    assert {variant(f"s{n}", "c1") for n in range(30)} == {0, 1, 2}


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("kind", REQUESTS)
@pytest.mark.parametrize("role", ROLES)
def test_subject_never_exceeds_60_characters(style, language, kind, role):
    text = subject(style, language, "X" * 40, "Finanzierungsrunde", role_name(role, language), kind)
    assert 0 < len(text) <= 60


def test_subjects_of_each_style():
    assert subject("direct", "en", "Example Robotics", "Series A", "Growth", "internship") == \
        "Example Robotics internship?"
    assert subject("direct", "de", "Example Robotics", "Series A", "Growth", "internship") == \
        "Praktikum bei Example Robotics?"
    assert subject("round", "de", "Example Robotics", "Seed", "Produkt", "internship") == \
        "Nach eurer Seed: Produkt bei Example Robotics"
    assert subject("round", "en", "Example Robotics", "Seed", "Product", "internship") == \
        "After your Seed: Product at Example Robotics"
    assert subject("formal", "en", "Example Robotics", "Seed", "Data", "internship") == \
        "Application: Data internship at Example Robotics"
    assert subject("formal", "de", "Example Robotics", "Seed", "Data", "part_time") == \
        "Bewerbung: Data-Teilzeit bei Example Robotics"
    assert subject("direct", "en", "Example Robotics", "Seed", "Data", "part_time") == \
        "Example Robotics part-time role?"


def test_a_long_name_drops_the_round_then_the_role():
    long_name = "Example Robotics And Autonomous Systems"            # 39 characters
    text = subject("round", "en", long_name, "growth round", "Business development", "internship")
    assert "growth round" not in text and len(text) <= 60
    assert subject("direct", "en", "X" * 60, "Seed", "Data", "internship") == "Internship?"


def test_suggested_style():
    hr = contact(person_name=None, address_type="careers", address="jobs@example.de")
    assert suggested_style(hr, round_(size_category="large")) == "formal"
    assert suggested_style(hr, round_(size_category="medium")) == "direct"
    assert suggested_style(contact(), round_(size_category="large")) == "direct"
    personal = contact(person_name=None, address_type="personal")
    assert suggested_style(personal, round_(size_category="large")) == "direct"
