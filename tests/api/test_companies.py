import re

from kaltstart.api.store import ListFilters
from tests.api.conftest import NOW, save_profile, sign_up_and_in, user_id


def names(page):
    return re.findall(r'<span class="row-title">([^<]+)</span>', page)


def test_the_list_shows_every_eligible_company_with_its_round(client, store, auth):
    sign_up_and_in(client)
    page = client.get("/companies?months=12").text
    rows, total = store.companies(ListFilters(), user_id(auth), NOW)
    assert names(page) == [r.name for r in rows]
    assert f"{total} companies" in page
    first = rows[0]
    assert first.country in page and (first.city or "") in page


def test_each_row_says_what_contact_exists(client, store, auth):
    sign_up_and_in(client)
    page = client.get("/companies?months=12").text
    assert "People named" in page and ("Careers address" in page or "General address" in page)
    assert "Person suggested" not in page


def test_a_full_company_is_hidden_and_no_counter_is_shown(client):
    sign_up_and_in(client)
    page = client.get("/companies?months=12").text
    assert "Glacier Systems" not in page
    assert "/3" not in page and "slots" not in page.lower()


def test_filters_in_the_query_string(client, store, auth):
    sign_up_and_in(client)
    page = client.get("/companies?country=Austria&months=12").text
    rows, _ = store.companies(ListFilters(countries=("Austria",)), user_id(auth), NOW)
    assert names(page) == [r.name for r in rows] and rows
    one = rows[0].name
    assert names(client.get(f"/companies?q={one.split()[0]}&months=12").text)[0].startswith(one.split()[0])


def test_the_profile_preferences_preset_the_filters(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, pref_country=["Germany"])
    page = client.get("/companies").text
    rows, _ = store.companies(ListFilters(countries=("Germany",)), user_id(auth), NOW)
    assert names(page) == [r.name for r in rows]
    assert 'value="Germany" selected' in page


def test_last_slot_is_flagged(client, store, auth):
    from tests.api.test_mails import keep
    keep(store, "a", "dev05")
    keep(store, "b", "dev05")
    sign_up_and_in(client)
    page = client.get("/companies?months=12").text
    row = page.split(store.company("dev05").name, 1)[1].split("</a>", 1)[0]
    assert "Last slot" in row


def test_an_excluded_company_has_no_page(client, store):
    sign_up_and_in(client)
    store.exclude_company("dev01")
    assert client.get("/companies/dev01").status_code == 404
    assert client.get("/companies/nope").status_code == 404


def test_the_count_does_not_claim_three_countries_when_filtered(client):
    sign_up_and_in(client)
    page = client.get("/companies?country=Germany&months=12").text
    assert "in Switzerland, Germany and Austria" not in page
    assert "companies match your filters" in page


def test_the_person_filter_in_the_page(client, store, auth):
    sign_up_and_in(client)
    page = client.get("/companies?months=12&person=1").text
    rows, _ = store.companies(ListFilters(with_person=True), user_id(auth), NOW)
    assert names(page) == [r.name for r in rows] and rows
    assert 'name="person" value="1" checked' in page
    assert "Only companies that name people" in page
    assert "General address" not in page and "Careers address" not in page


def test_each_row_shows_its_size_and_the_sizes_are_explained(client):
    sign_up_and_in(client)
    page = client.get("/companies?months=12").text
    assert 'class="size size-small"' in page or 'class="size size-medium"' in page
    for words in ("Small", "Medium", "Large", "founders read applications themselves",
                  "heads of product, growth or sales", "recruiter"):
        assert words in page, words


def test_the_list_opens_with_a_kicker(client):
    sign_up_and_in(client)
    assert 'class="kicker"' in client.get("/companies").text
