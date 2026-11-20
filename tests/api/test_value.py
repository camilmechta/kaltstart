"""Show the value once signed in (design 2026-11-19): row hooks, "For you",
the progress strip."""

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from kaltstart.api.app import create_app
from kaltstart.api.auth import FakeAuth
from kaltstart.api.store import EmailRow, InMemoryAppStore, PersonRow
from tests.api.conftest import NOW, REMOVAL, save_profile, sign_up_and_in, user_id
from tests.api.test_mails import keep
from tests.api.test_store import company

HEAD_GROWTH = PersonRow("Anna Muster", "Head of Growth", ("growth",), "head",
                        "https://example.ch/team", date(2026, 11, 1))
CTO = PersonRow("Ben Probe", "CTO", ("leadership",), "head", "https://example.ch/team",
                date(2026, 11, 1))


def info(n):
    return [EmailRow(f"info@c{n}.example.ch", "generic", f"https://c{n}.example.ch/")]


@pytest.fixture
def store():
    s = InMemoryAppStore(invitation="dev")
    s.add_company(company(1, name="Fresh Growth Co", days=5), emails=info(1), people=[HEAD_GROWTH])
    s.add_company(company(2, name="Old Growth Co", days=60), emails=info(2), people=[HEAD_GROWTH])
    s.add_company(company(3, name="Fresh Plain Co", days=3), emails=info(3), people=[CTO])
    s.add_company(company(4, name="Big Growth Co", days=2, size="large"), emails=info(4),
                  people=[HEAD_GROWTH])
    s.add_company(company(5, name="Week Co", days=7), emails=info(5), people=[])
    return s


@pytest.fixture
def auth():
    return FakeAuth()


@pytest.fixture
def client(store, auth):
    app = create_app(store, auth, session_secret="test-secret", removal_contact=REMOVAL,
                     now=lambda: NOW)
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


def row(page, name):
    rows = page.split('<ul class="rows">', 1)[1]
    return rows.split(name, 1)[1].split("</li>", 1)[0]


# --- C: row hooks -------------------------------------------------------------

def test_a_recent_round_says_how_long_ago(client):
    sign_up_and_in(client)
    page = client.get("/companies?months=12").text
    assert "Raised 5 days ago" in row(page, "Fresh Growth Co")
    assert "Raised 1 week ago" in row(page, "Week Co")
    assert "Raised" not in row(page, "Old Growth Co")


@pytest.mark.parametrize("days,text", [(0, "Raised today"), (1, "Raised yesterday"),
                                       (6, "Raised 6 days ago"), (7, "Raised 1 week ago"),
                                       (29, "Raised 4 weeks ago"), (30, None)])
def test_the_age_wording(days, text):
    from kaltstart.api.pages import raised_ago
    assert raised_ago((NOW - timedelta(days=days)).date(), NOW) == text


def test_a_person_of_the_students_field_is_named_on_the_row(client):
    sign_up_and_in(client)
    save_profile(client)                       # target role: growth
    page = client.get("/companies?months=12").text
    assert "Head of Growth named: your field" in row(page, "Fresh Growth Co")
    assert "your field" not in row(page, "Fresh Plain Co")
    assert "Head of Growth" not in row(page, "Big Growth Co")


# --- B: For you -------------------------------------------------------------

def for_you(page):
    if 'class="for-you"' not in page:
        return []
    block = page.split('class="for-you"', 1)[1].split("</section>", 1)[0]
    return re.findall(r'class="for-you-name">([^<]+)<', block)


def test_for_you_needs_a_complete_profile(client):
    sign_up_and_in(client)
    assert for_you(client.get("/companies").text) == []


def test_for_you_picks_fresh_companies_with_someone_of_the_field(client):
    sign_up_and_in(client)
    save_profile(client, pref_country="")
    page = client.get("/companies").text
    picked = for_you(page)
    assert picked == ["Fresh Growth Co", "Old Growth Co"]     # newest first; no large company
    assert len(picked) <= 3
    assert "Anna Muster, Head of Growth: your field" in page.split('class="for-you"', 1)[1]


def test_for_you_skips_companies_already_written_to(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, pref_country="")
    keep(store, user_id(auth), "c1")
    assert "Fresh Growth Co" not in for_you(client.get("/companies").text)


def test_for_you_is_not_shown_on_a_search(client):
    sign_up_and_in(client)
    save_profile(client, pref_country="")
    assert for_you(client.get("/companies?q=Co").text) == []


# --- D: progress --------------------------------------------------------------

def test_progress_replaces_get_started(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, pref_country="")
    me = user_id(auth)
    first = keep(store, me, "c1")
    keep(store, me, "c3")
    store.set_status(me, first, "human_reply", NOW)
    page = client.get("/companies").text
    assert "Get started" not in page
    assert "Your applications: 2 kept · 1 sent · 1 reply" in page


def test_a_no_reply_mail_counts_as_sent_not_as_a_reply(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, pref_country="")
    me = user_id(auth)
    first = keep(store, me, "c1")
    store.set_status(me, first, "sent", NOW)
    store.set_status(me, first, "no_reply", NOW)
    assert "Your applications: 1 kept · 1 sent · 0 replies" in client.get("/companies").text
