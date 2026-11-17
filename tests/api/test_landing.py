from kaltstart.api.store import ListFilters
from tests.api.conftest import NOW, save_profile, sign_up_and_in, user_id


def test_visitors_land_on_a_page_that_explains_the_product(client, store):
    page = client.get("/")
    assert page.status_code == 200
    text = page.text
    for words in ("Write to startups while the money is fresh", "The right moment",
                  "The right person", "A mail that stands out", "How it works",
                  "3 mails", "the part that gets you hired is yours"):
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
    assert "Get started" in page
    panel = page.split('class="get-started"', 1)[1].split("</section>", 1)[0]
    assert '<a class="gs-step todo" href="/profile">' in panel
    assert '<a class="gs-step todo" href="#companies">' in panel
    assert 'class="gs-number">1<' in panel and 'class="gs-number">2<' in panel
    assert 'id="companies"' in page


def test_the_profile_step_is_ticked_once_done(client):
    sign_up_and_in(client)
    save_profile(client)
    panel = client.get("/companies").text.split('class="get-started"', 1)[1].split("</section>", 1)[0]
    assert panel.count('gs-step done') == 1 and panel.count('gs-step todo') == 1


def test_the_panel_disappears_after_the_first_kept_mail(client, store, auth):
    from tests.api.test_mails import keep
    sign_up_and_in(client)
    save_profile(client)
    keep(store, user_id(auth), "dev01")
    assert "Get started" not in client.get("/companies").text


def test_the_landing_page_shows_an_example_of_the_product(client):
    text = client.get("/").text
    assert "the week they raise" not in text
    example = text.split('product-example"', 1)[1].split("</section>", 1)[0]
    assert 'class="row' in example and 'class="mail-preview' in example
    assert "invented" in example.lower()
    assert 'class="feature"' not in text


def test_the_hero_rises_in_order(client):
    hero = client.get("/").text.split('class="hero"', 1)[1].split("</section>", 1)[0]
    assert hero.count('class="rise') >= 4 or hero.count(' rise"') + hero.count('class="rise') >= 4
