import pytest
from fastapi.testclient import TestClient

from kaltstart.api.app import create_app
from kaltstart.api.auth import FakeAuth
from kaltstart.api.store import InMemoryAppStore
from tests.api.conftest import NOW, csrf, save_profile, sign_up_and_in, user_id
from tests.api.test_compose import ANNA, BEN, C1, EMAILS
from tests.api.test_mails import keep


@pytest.fixture
def store():
    store = InMemoryAppStore(invitation="dev")
    store.add_company(C1, emails=EMAILS, people=[BEN, ANNA])
    return store


@pytest.fixture
def client(store):
    app = create_app(store, FakeAuth(), session_secret="s", removal_contact="r@example.com",
                     now=lambda: NOW)
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def auth(client):
    return client.app.state.auth


def ready(client):
    sign_up_and_in(client)
    save_profile(client)


def post(client, action, **fields):
    data = {"style": "direct", "language": "en", "showcase": "1", "company_line": ""}
    data.update(fields)
    data["csrf"] = csrf(client, "/companies/c1")
    return client.post(f"/companies/c1/{action}", data=data)


def test_the_page_shows_the_company_and_the_choices(client):
    ready(client)
    page = client.get("/companies/c1").text
    assert C1.name in page and "€2M seed round" in page and C1.description in page
    assert "Anna Muster" in page and "Head of Growth" in page and "https://c1.example.ch/team" in page
    assert "Ben Probe" in page
    for value in ("suggested", "other_on_list", "typed", "team"):
        assert f'value="{value}"' in page
    assert 'data-max-words="35"' in page and "takes one of the 3 slots" not in page
    assert "Keep this mail" not in page


def test_nothing_is_preselected_as_the_recipient(client):
    ready(client)
    page = client.get("/companies/c1").text
    assert 'name="choice" value="suggested" checked' not in page


def test_a_preview_needs_a_choice(client, store):
    ready(client)
    page = post(client, "preview")
    assert page.status_code == 400 and "Choose who you write to" in page.text


def test_the_preview_shows_the_mail_and_stores_nothing(client, store):
    ready(client)
    page = post(client, "preview", choice="suggested")
    assert page.status_code == 200
    assert "Hi Anna!" in page.text and "Keep this mail" in page.text
    assert "anna.muster@c1.example.ch" not in page.text      # shown once kept (D77)
    assert store.all_mails() == []


def test_an_incomplete_profile_is_named_with_a_link(client):
    sign_up_and_in(client)
    page = post(client, "preview", choice="team")
    assert page.status_code == 400
    assert "Complete your profile" in page.text and 'href="/profile"' in page.text


def test_a_company_sentence_over_35_words_is_refused(client):
    ready(client)
    page = post(client, "preview", choice="team", company_line=" ".join(["word"] * 36))
    assert page.status_code == 400 and "35 words" in page.text


def test_keeping_stores_the_same_mail_and_opens_it(client, store, auth):
    ready(client)
    preview = post(client, "preview", choice="suggested").text
    response = post(client, "keep", choice="suggested")
    assert response.status_code == 303 and response.headers["location"].startswith("/mails/")
    mail = store.all_mails()[0]
    assert (mail.student_id, mail.person_name, mail.address, mail.person_choice) == (
        user_id(auth), "Anna Muster", "anna.muster@c1.example.ch", "suggested")
    assert mail.body.split("\n")[0] in preview and mail.subject in preview


def test_posted_addresses_and_names_are_ignored(client, store):
    ready(client)
    post(client, "keep", choice="suggested", address="evil@example.com",
         person_name="Somebody Else", address_type="personal")
    mail = store.all_mails()[0]
    assert (mail.address, mail.person_name) == ("anna.muster@c1.example.ch", "Anna Muster")


def test_keeping_twice_for_one_company_is_refused(client, store):
    ready(client)
    post(client, "keep", choice="team")
    page = post(client, "keep", choice="suggested")
    assert page.status_code == 409 and "already wrote to this company" in page.text
    assert len(store.all_mails()) == 1


def test_a_full_company_is_refused_at_preview_with_the_date(client, store):
    for student in ("a", "b", "c"):
        keep(store, student, "c1")
    ready(client)
    page = post(client, "preview", choice="team")
    assert page.status_code == 409 and "3 mails" in page.text and "16 December 2026" in page.text


def test_another_person_on_the_list(client, store):
    ready(client)
    post(client, "keep", choice="other_on_list", person="0")
    mail = store.all_mails()[0]
    assert (mail.person_name, mail.address) == ("Ben Probe", "jobs@c1.example.ch")


def test_a_typed_name(client, store):
    ready(client)
    post(client, "keep", choice="typed", typed_name="Clara Vorlage")
    mail = store.all_mails()[0]
    assert (mail.person_name, mail.address, mail.person_choice) == (
        "Clara Vorlage", "jobs@c1.example.ch", "typed")


def test_the_company_page_says_what_its_size_means(client):
    ready(client)
    page = client.get("/companies/c1").text                 # C1 is medium
    assert 'class="size size-medium"' in page
    assert "Team leads" in page


def test_the_page_explains_who_the_suggested_person_is(client):
    ready(client)
    page = client.get("/companies/c1").text
    assert "Why Anna" in page and "matches your target role: Growth" in page
    assert "found on the company's own website" in page


def test_no_stepper_and_choices_are_cards(client):
    ready(client)
    page = client.get("/companies/c1").text
    assert 'class="stepper"' not in page and page.count('class="option-card') == 4
    assert "Keep it, then copy it" not in page


def test_after_a_preview_the_third_step_appears(client):
    ready(client)
    assert "Keep it, then copy it" in post(client, "preview", choice="team").text


def test_a_missing_choice_is_said_next_to_the_button(client):
    ready(client)
    page = post(client, "preview").text
    step = page.split('id="generate"', 1)[1]
    assert 'aria-live="polite"' in step.split("Generate my mail", 1)[0]
    assert "Choose who you write to" in step.split("Generate my mail", 1)[0]


def test_styles_are_chips_that_say_what_they_do(client):
    ready(client)
    page = client.get("/companies/c1").text
    for value, hint in (("direct", "Best for founders"), ("round", "15-minute call"),
                        ("formal", "large companies")):
        assert f'name="style" value="{value}"' in page and hint in page
    assert page.count('class="role-card style-card"') == 3
    assert page.count('class="chip-toggle"') >= 2   # the two languages


def test_the_style_is_round_when_the_suggested_person_recruits(client, store):
    from kaltstart.api.store import PersonRow
    from tests.api.test_compose import C1, EMAILS
    from dataclasses import replace
    store.add_company(replace(C1, id="c2", name="Recruit Co"), emails=EMAILS, people=[
        PersonRow("Noah Beispiel", "Talent Acquisition Manager", ("recruiting",), "manager",
                  "https://c1.example.ch/team", NOW)])
    ready(client)
    page = client.get("/companies/c2").text
    assert 'name="style" value="round" checked' in page
    assert 'name="style" value="direct" checked' in client.get("/companies/c1").text


def test_without_a_profile_the_page_asks_for_it_before_suggesting(client):
    sign_up_and_in(client)
    page = client.get("/companies/c1").text
    assert "Complete your profile" in page and 'href="/profile"' in page
    assert "Why Anna" not in page


def test_the_suggested_person_is_not_repeated_under_someone_else(client):
    ready(client)
    page = client.get("/companies/c1").text
    other = page.split('name="person"', 1)[1].split("</select>", 1)[0]
    assert "Ben Probe" in other and "Anna Muster" not in other


def test_the_page_says_the_address_comes_when_the_mail_is_kept(client):
    ready(client)
    page = client.get("/companies/c1").text
    assert "You get the address when you keep your mail." in page
    assert "A free preview: nothing is kept yet, and the address shows once you keep it." in page


def test_the_preview_never_shows_the_address(client):
    ready(client)
    for choice in ("suggested", "team"):
        page = post(client, "preview", choice=choice).text
        assert "@c1.example.ch" not in page, choice
        assert "Shown once you keep this mail" in page
        assert 'class="mail-preview reveal"' in page


def test_the_kept_mail_reveals_its_address(client, store):
    ready(client)
    response = post(client, "keep", choice="team")
    page = client.get(response.headers["location"]).text
    assert 'class="mail-address unlock"' in page and "@c1.example.ch" in page



# --- sending limits and variation -------------------------------------------

def reserve(store, student, days, company=None, **changes):
    from dataclasses import replace
    from datetime import timedelta
    from kaltstart.api.store import NewMail
    c = company or C1
    mail = NewMail(company_id=c.id, round_id=c.round_id, address="info@c1.example.ch",
                   address_type="generic", person_name=None, person_key=None,
                   person_choice="team", person_source_url=None, style="direct",
                   language="en", company_line=None, used_company_line=False,
                   subject="S", body="B", size_category=c.size_category)
    return store.reserve(student, replace(mail, **changes), NOW - timedelta(days=days))


def test_a_company_whose_round_is_full_is_hidden(client, store):
    for n in range(9):                                   # medium: 9 per round
        reserve(store, f"other{n}", 40 * (9 - n))
    ready(client)
    assert C1.name not in client.get("/companies?months=12").text


def test_the_round_full_refusal_is_said(client, store):
    for n in range(9):
        reserve(store, f"other{n}", 40 * (9 - n))
    ready(client)
    page = post(client, "preview", choice="team")
    assert page.status_code == 409
    assert "all the mails Kaltstart allows for its current funding round" in page.text


def test_the_speed_refusal_names_the_date(client, store, auth):
    ready(client)
    for n in range(10):
        reserve(store, user_id(auth), 6 - n * 0.5, company_id=f"x{n}", round_id=f"rx{n}")
        store.set_status(user_id(auth), store.all_mails()[-1].id, "sent", NOW)
    page = post(client, "preview", choice="team")
    assert page.status_code == 409
    assert "You kept 10 mails this week. You can keep a new one on 17 November 2026." in page.text


def test_places_left_are_shown(client, store):
    reserve(store, "a", 2)
    ready(client)
    assert "2 places left" in client.get("/companies/c1").text
    reserve(store, "b", 1)
    assert "1 place left" in client.get("/companies/c1").text


def test_the_second_kept_mail_to_a_company_uses_the_next_variant(client, store, auth):
    ready(client)
    first = reserve(store, "other", 3, subject="Example internship?")
    post(client, "keep", choice="team")
    mine = [m for m in store.all_mails() if m.student_id == user_id(auth)][0]
    assert mine.variant == 1 and mine.size_category == C1.size_category
    assert mine.subject != "Example internship?" and isinstance(first, str)


def test_a_full_round_does_not_send_the_student_to_my_mails(client, store):
    for n in range(9):
        reserve(store, f"other{n}", 40 * (9 - n))
    ready(client)
    assert "Open My mails" not in post(client, "preview", choice="team").text
