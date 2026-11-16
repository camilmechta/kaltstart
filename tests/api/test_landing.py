from kaltstart.api.store import ListFilters
from tests.api.conftest import NOW, save_profile, sign_up_and_in, user_id


def test_visitors_land_on_a_page_that_explains_the_product(client, store):
    page = client.get("/")
    assert page.status_code == 200
    text = page.text
    for words in ("Write to startups the week they raise money", "The right moment",
                  "The right person", "A mail that stands out", "How it works",
                  "3 mails", "never sends"):
        assert words in text, words
    assert 'href="/signup"' in text and 'href="/signin"' in text
    _rows, total = store.companies(ListFilters(), "", NOW)
    assert f"{total} companies" in text


def test_signed_in_students_go_straight_to_the_companies(client):
    sign_up_and_in(client)
    response = client.get("/")
    assert response.status_code == 303 and response.headers["location"] == "/companies"


def test_the_sign_in_page_links_back_to_the_landing_page(client):
    assert 'href="/"' in client.get("/signin").text


def test_a_new_student_sees_how_to_get_started(client):
    sign_up_and_in(client)
    page = client.get("/companies").text
    assert "Get started" in page and 'href="/profile"' in page
    panel = page.split('class="get-started"', 1)[1].split("</section>", 1)[0]
    assert 'class="todo"' in panel and 'class="done"' not in panel


def test_the_profile_step_is_ticked_once_done(client):
    sign_up_and_in(client)
    save_profile(client)
    panel = client.get("/companies").text.split('class="get-started"', 1)[1].split("</section>", 1)[0]
    assert panel.count('class="done"') == 1 and panel.count('class="todo"') == 1


def test_the_panel_disappears_after_the_first_kept_mail(client, store, auth):
    from tests.api.test_mails import keep
    sign_up_and_in(client)
    save_profile(client)
    keep(store, user_id(auth), "dev01")
    assert "Get started" not in client.get("/companies").text
