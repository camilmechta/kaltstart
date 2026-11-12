import pytest
from kaltstart.ingestion.cleaning import (
    clean_city, clean_investors, clean_website, size_category)

@pytest.mark.parametrize("raw,expected", [
    ("Zurich ", ("Zurich", None)),
    ("  Zürich", ("Zurich", None)),
    ("Berne", ("Bern", None)),
    ("Vaud", (None, "Vaud")),
    ("Obwalden", (None, "Obwalden")),
    ("St.  Gallen", ("St. Gallen", None)),
    ("Eggersriet", ("Eggersriet", None)),   # unknown: kept as is
    ("", (None, None)),
    (None, (None, None)),
])
def test_clean_city(raw, expected):
    assert clean_city(raw) == expected

def test_clean_investors_strips_and_dedupes_keeping_order():
    assert clean_investors(["Tenity ", "Altair Capital", "Tenity", ""]) == [
        "Tenity", "Altair Capital"]
    assert clean_investors(None) == []

@pytest.mark.parametrize("stage,amount,expected", [
    ("Pre-Seed", 50_000_000, "small"),      # a known stage wins
    ("Seed", None, "small"),
    ("Series A", None, "medium"),
    ("Series B", 1_000_000, "large"),
    ("Series C", None, "large"),
    ("Series D+", None, "large"),
    ("Growth/Late", None, "large"),
    ("Other", 6_999_999, "small"),
    ("Other", 7_000_000, "medium"),
    ("Other", 20_000_000, "medium"),
    ("Other", 20_000_001, "large"),
    ("Grant", 150_000, "small"),            # Grant and Debt: by amount
    ("Debt", 25_000_000, "large"),
    ("Other", None, "small"),               # neither stage nor amount
    (None, None, "small"),
    ("Brand New Stage", 10_000_000, "medium"),
])
def test_size_category(stage, amount, expected):
    assert size_category(stage, amount) == expected

@pytest.mark.parametrize("raw,expected", [
    ("https://www.lightframe.tech/", "https://www.lightframe.tech"),
    (" www.example.ch ", "https://www.example.ch"),
    ("http://example.de/path", "http://example.de/path"),
    ("", None), (None, None), ("not a url", None), ("[abc.com", None),
])
def test_clean_website(raw, expected):
    assert clean_website(raw) == expected
