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
