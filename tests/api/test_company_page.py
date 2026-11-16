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
    assert "anna.muster@c1.example.ch" in page.text
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
    assert 'class="size size-medium"' in page and "Series A" in page
    assert "heads of product, growth or sales" in page
