from kaltstart.api.store import ListFilters
from tests.api.conftest import NOW, save_profile, sign_up_and_in, user_id


def test_visitors_land_on_a_page_that_explains_the_product(client, store):
    page = client.get("/")
    assert page.status_code == 200
    text = page.text
    for words in ("Internships that are never posted.",
                  "Startups that just raised money hire in the next months, but most never "
                  "post the job.", "Roles no one has posted yet", "The right person, not a form",
                  "Two minutes, not two hours", "New rounds every night",
                  "The right moment", "The right person", "A mail that stands out",
                  "How it works", "3 mails", "the part that gets you hired is yours"):
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



def test_the_example_is_honest_and_shows_linkedin(client):
    import html
    from kaltstart.mailgen.linkedin import note_length
    text = html.unescape(client.get("/").text)
    example = text.split('product-example"', 1)[1].split("</section>", 1)[0]
    assert "mara.keller@" not in example and "hello@glacier.example.ch" in example
    assert "PS:" in example and "Or on LinkedIn" in example
    note = example.split('class="example-note-text">', 1)[1].split("<", 1)[0]
    assert 0 < note_length(note) <= 200


# Design review of the landing page (2026-11-19).
def test_shared_links_have_a_description_a_preview_and_an_icon(client):
    page = client.get("/").text
    assert '<meta name="description" content="Startups that just raised money hire' in page
    assert '<meta property="og:title" content="Kaltstart · Internships that are never posted">' in page
    assert '<meta property="og:image" content="https://testserver/static/og.png">' in page
    assert '<meta name="twitter:card" content="summary_large_image">' in page
    assert '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">' in page
    assert client.get("/static/og.png").status_code == 200
    assert client.get("/static/favicon.svg").status_code == 200


def test_every_page_has_the_icon(client):
    for path in ("/signin", "/about", "/privacy"):
        assert 'href="/static/favicon.svg"' in client.get(path).text, path


def test_visitors_without_a_code_know_what_to_do(client):
    import html
    import re
    hero = html.unescape(client.get("/").text).split('class="hero"', 1)[1].split("</section>", 1)[0]
    assert "No invitation code yet? Ask at removal@example.com." in re.sub(r"<[^>]+>", "", hero)
    assert 'href="mailto:removal@example.com"' in hero


def test_how_it_works_is_three_short_steps_not_cards(client):
    how = client.get("/").text.split('id="how-title"', 1)[1].split("</section>", 1)[0]
    assert 'class="how-steps"' in how and "how-card" not in how


def test_the_hero_text_keeps_short_lines():
    from pathlib import Path
    css = (Path(__file__).parents[2] / "src" / "kaltstart" / "api" / "static" / "app.css").read_text()
    assert ".hero-sub { font-size: var(--text-lg); line-height: 30px; color: var(--muted); max-width: 52ch; }" in css


def test_the_sign_up_page_and_the_last_call_say_how_to_get_a_code(client):
    import html
    import re
    hint = "No invitation code yet? Ask at removal@example.com."
    signup = html.unescape(client.get("/signup").text)
    assert hint in re.sub(r"<[^>]+>", "", signup)
    assert 'href="mailto:removal@example.com"' in signup.split('id="code-help"', 1)[1]
    final = html.unescape(client.get("/").text).split('id="final-title"', 1)[1].split("</section>", 1)[0]
    assert hint in re.sub(r"<[^>]+>", "", final)
