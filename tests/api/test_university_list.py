"""The university field (D113): a list of the main universities of
Switzerland, Germany and Austria, and "Other" with a field of its own."""

import re
from pathlib import Path

import pytest

from kaltstart.api.universities import UNIVERSITIES, listed
from kaltstart.mailgen.models import MAX_UNIVERSITY_CHARS
from tests.api.conftest import save_profile, sign_up_and_in, user_id

SCRIPT = (Path(__file__).parents[2] / "src/kaltstart/api/static/app.js").read_text()


def test_three_countries_and_every_name_fits_a_mail():
    assert [country for country, _ in UNIVERSITIES] == ["Switzerland", "Germany", "Austria"]
    values = [value for _, unis in UNIVERSITIES for value, _ in unis]
    assert len(values) == len(set(values)) and len(values) >= 25
    assert all(len(value) <= MAX_UNIVERSITY_CHARS for value in values)
    assert {"HSG", "ETH Zurich", "EPFL", "TUM", "WU Vienna"} <= set(values)


def test_the_page_shows_the_list_grouped_by_country_and_other(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    select = re.search(r'<select [^>]*name="university".*?</select>', page, re.S).group(0)
    for country in ("Switzerland", "Germany", "Austria"):
        assert f'<optgroup label="{country}">' in select
    assert '<option value="HSG">University of St. Gallen (HSG)</option>' in select
    assert '<option value="other">Other, not listed</option>' in select
    assert 'name="university_other"' in page and 'data-show-when="university=other"' in page


def test_a_listed_university_is_saved_by_its_short_name(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, university="TUM")
    assert store.profile(user_id(auth)).university == "TUM"


def test_other_saves_the_typed_name(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, university="other", university_other="  Hochschule  Luzern ")
    assert store.profile(user_id(auth)).university == "Hochschule Luzern"


@pytest.mark.parametrize("typed,message", [
    ("", "Type your university, or pick it in the list."),
    ("x" * 31, f"University: at most {MAX_UNIVERSITY_CHARS} characters."),
])
def test_other_needs_a_name_that_fits(client, store, auth, typed, message):
    sign_up_and_in(client)
    page = save_profile(client, university="other", university_other=typed)
    assert page.status_code == 400 and message in page.text


def test_a_saved_listed_university_comes_back_selected(client):
    sign_up_and_in(client)
    save_profile(client, university="EPFL")
    page = client.get("/profile").text
    assert '<option value="EPFL" selected>' in page
    other = re.search(r'<label [^>]*data-show-when="university=other"[^>]*>', page).group(0)
    assert "hidden" in other


def test_a_saved_unlisted_university_comes_back_as_other(client):
    sign_up_and_in(client)
    save_profile(client, university="other", university_other="Hochschule Luzern")
    page = client.get("/profile").text
    assert '<option value="other" selected>' in page
    assert 'name="university_other" value="Hochschule Luzern"' in page
    other = re.search(r'<label [^>]*data-show-when="university=other"[^>]*>', page).group(0)
    assert "hidden" not in other


def test_listed_is_true_only_for_the_list():
    assert listed("HSG") and not listed("Hochschule Luzern") and not listed("")


def test_the_script_shows_the_other_field_for_a_select():
    assert 'select[name="' in SCRIPT


def test_a_name_typed_with_the_list_left_empty_is_kept(client, store, auth):
    # Review 2026-11-25: without JavaScript the field shows for a new student.
    sign_up_and_in(client)
    save_profile(client, university="", university_other="Hochschule Luzern")
    assert store.profile(user_id(auth)).university == "Hochschule Luzern"
