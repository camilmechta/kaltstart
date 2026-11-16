from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from kaltstart.api.app import create_app
from kaltstart.api.auth import FakeAuth
from kaltstart.api.seed import seeded_store

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
CODE = "dev"
REMOVAL = "removal@example.com"


@pytest.fixture
def store():
    return seeded_store(NOW)


@pytest.fixture
def auth():
    return FakeAuth()


@pytest.fixture
def client(store, auth):
    app = create_app(store, auth, session_secret="test-secret", removal_contact=REMOVAL,
                     now=lambda: NOW)
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


def csrf(client, path="/signin"):
    page = client.get(path).text
    marker = 'name="csrf" value="'
    return page.split(marker, 1)[1].split('"', 1)[0]


def sign_up_and_in(client, email="lea@example.com", password="a-long-password"):
    client.post("/signup", data={"email": email, "password": password, "code": CODE,
                                 "csrf": csrf(client, "/signup")})
    response = client.post("/signin", data={"email": email, "password": password,
                                            "csrf": csrf(client)})
    assert response.status_code == 303, response.text
    return response


def user_id(auth, email="lea@example.com"):
    return auth.users[email][2]


PROFILE = {
    "first_name": "Lea", "last_name": "Beispiel", "programme": "Business Innovation",
    "lang_en": "on", "target_role": "growth", "request": "internship",
    "start_date": "2027-04-01", "duration_months": "3", "workload_percent": "",
    "link": "https://example.com/lea",
    "showcase1_en": "I grew a student newsletter from 0 to 4000 readers in one year.",
    "showcase1_de": "", "showcase2_en": "", "showcase2_de": "",
    "pref_country": ["Switzerland", "Germany"],
}


def save_profile(client, **changes):
    data = dict(PROFILE)
    data.update(changes)
    data["csrf"] = csrf(client, "/profile")
    return client.post("/profile", data=data)
