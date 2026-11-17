"""Fixes after the final review of Phase 4 (2026-11-17)."""

import inspect
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kaltstart.api.app import create_app
from kaltstart.api.auth import FakeAuth
from kaltstart.api.session import client_ip
from kaltstart.api.store import CompanyRow, EmailRow, PersonRow
from tests.api.conftest import CODE, NOW, REMOVAL, csrf, save_profile, sign_up_and_in, user_id

ROOT = Path(__file__).parents[2]


def make_client(store, auth, **options):
    app = create_app(store, auth, session_secret="test-secret", removal_contact=REMOVAL,
                     now=lambda: NOW, **options)
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


def signup(client, code, email="x@example.com", forwarded=None):
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    return client.post("/signup", data={"email": email, "password": "a-long-password",
                                        "code": code, "csrf": csrf(client, "/signup")},
                       headers=headers)


# --- 1. the client's address cannot be faked --------------------------------

class FakeRequest:
    def __init__(self, forwarded=None, host="10.0.0.1"):
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}
        self.client = type("C", (), {"host": host})()


def test_the_client_address_is_the_one_our_proxy_added():
    assert client_ip(FakeRequest("6.6.6.6, 1.2.3.4"), hops=1) == "1.2.3.4"
    assert client_ip(FakeRequest("6.6.6.6, 1.2.3.4, 5.5.5.5"), hops=2) == "1.2.3.4"
    assert client_ip(FakeRequest(None), hops=1) == "10.0.0.1"
    assert client_ip(FakeRequest("6.6.6.6"), hops=0) == "10.0.0.1"


def test_a_faked_forwarded_address_does_not_reset_the_sign_up_limit(store, auth):
    client = make_client(store, auth, proxy_hops=1)
    for n in range(10):
        signup(client, "wrong", forwarded=f"9.9.9.{n}, 1.2.3.4")
    assert signup(client, "wrong", forwarded="7.7.7.7, 1.2.3.4").status_code == 429


def test_too_many_wrong_codes_close_sign_up_for_everyone(store, auth):
    client = make_client(store, auth, proxy_hops=1)
    for n in range(30):
        signup(client, "wrong", forwarded=f"1.2.{n // 10}.{n}")
    assert signup(client, CODE, forwarded="8.8.8.8").status_code == 429


def test_sign_in_attempts_are_limited_per_address(store, auth):
    client = make_client(store, auth, proxy_hops=1)
    sign_up_and_in(client)
    for n in range(10):
        client.post("/signin", data={"email": "lea@example.com", "password": "wrong-one",
                                     "csrf": csrf(client)}, headers={"X-Forwarded-For": f"4.4.4.{n}"})
    right = client.post("/signin", data={"email": "lea@example.com", "password": "a-long-password",
                                         "csrf": csrf(client)}, headers={"X-Forwarded-For": "5.5.5.5"})
    assert right.status_code == 429


# --- 2. links from data and security headers ---------------------------------

def test_only_web_links_are_rendered(store, auth):
    evil = "javascript://x.example.com%0aalert(1)"
    from tests.api.test_compose import C1
    from dataclasses import replace
    store.add_company(replace(C1, id="evil", name="Evil Co", website=evil),
                      emails=[EmailRow("info@evil.example.ch", "generic", evil)],
                      people=[PersonRow("Anna Muster", "Head of Growth", ("growth",), "head", evil, NOW)])
    client = make_client(store, auth)
    sign_up_and_in(client)
    save_profile(client)
    page = client.get("/companies/evil").text
    assert "javascript:" not in page


def test_the_ingestion_keeps_only_web_links():
    from kaltstart.ingestion.cleaning import clean_website
    assert clean_website("javascript://x.example.com%0aalert(1)") is None
    assert clean_website("ftp://files.example.com") is None
    assert clean_website("http://example.com") == "http://example.com"
    assert clean_website("example.com") == "https://example.com"


def test_every_page_sends_the_security_headers(client):
    headers = client.get("/").headers
    csp = headers["content-security-policy"]
    for part in ("default-src 'self'", "script-src 'self'", "frame-ancestors 'none'",
                 "object-src 'none'", "base-uri 'none'", "form-action 'self'"):
        assert part in csp, part
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"


# --- 3. no route blocks the server, fewer calls ------------------------------

def test_no_route_runs_on_the_event_loop(client):
    for route in client.app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None and getattr(route, "path", "").startswith("/static") is False:
            assert not inspect.iscoroutinefunction(endpoint), route.path


class CountingStore:
    """Wraps a store and counts the calls the pages make."""

    def __init__(self, inner):
        self._inner, self.calls = inner, {}

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def counted(*args, **kwargs):
            self.calls[name] = self.calls.get(name, 0) + 1
            return attr(*args, **kwargs)
        return counted


def test_the_company_list_reads_contacts_once(store, auth):
    counting = CountingStore(store)
    client = make_client(counting, auth)
    sign_up_and_in(client)
    counting.calls.clear()
    client.get("/companies?months=12")
    assert counting.calls.get("people", 0) == 0 and counting.calls.get("emails", 0) == 0
    assert counting.calls.get("contact_summary") == 1


def test_a_page_does_not_read_every_mail_for_the_counter(store, auth):
    counting = CountingStore(store)
    client = make_client(counting, auth)
    sign_up_and_in(client)
    counting.calls.clear()
    client.get("/profile")
    assert counting.calls.get("mail_records", 0) == 0


def test_static_files_skip_the_session(store, auth):
    counting_auth = FakeAuth()
    client = make_client(store, counting_auth)
    sign_up_and_in(client)
    calls = []
    original = counting_auth.user_id
    counting_auth.user_id = lambda token: calls.append(token) or original(token)
    response = client.get("/static/app.css")
    assert response.status_code == 200 and calls == [] and "set-cookie" not in response.headers


# --- 4. the session ----------------------------------------------------------

def test_a_refreshed_session_is_kept_by_any_response(client, store, auth):
    from tests.api.test_mails import keep
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    token = csrf(client, "/mails")
    auth._access.clear()                        # the access token expired
    response = client.post(f"/mails/{mail_id}/copied", data={"csrf": token})
    assert response.status_code == 204 and "set-cookie" in response.headers
    assert client.get("/companies").status_code == 200   # still signed in


def test_sign_out_revokes_the_session(client):
    sign_up_and_in(client)
    stolen = client.cookies.get("kaltstart")
    client.post("/signout", data={"csrf": csrf(client, "/companies")})
    client.cookies.set("kaltstart", stolen, domain="testserver")
    assert client.get("/companies").status_code == 303


def test_the_csrf_token_changes_at_sign_in_and_sign_out(client):
    before = csrf(client)
    sign_up_and_in(client)
    signed_in = csrf(client, "/companies")
    client.post("/signout", data={"csrf": signed_in})
    after = csrf(client)
    assert len({before, signed_in, after}) == 3


# --- 5. small points ----------------------------------------------------------

def test_a_status_change_never_redirects_to_another_site(client, store, auth):
    from tests.api.test_mails import keep
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    response = client.post(f"/mails/{mail_id}/status", data={
        "status": "sent", "back": "https://evil.example.com", "csrf": csrf(client, "/mails")})
    assert response.headers["location"].startswith("/")


def test_a_mail_id_that_is_not_a_uuid_is_not_found(client):
    sign_up_and_in(client)
    assert client.get("/mails/not-a-uuid").status_code == 404


def test_a_csrf_token_with_other_characters_is_refused(client):
    response = client.post("/signin", data={"email": "a@example.com", "password": "x",
                                            "csrf": "éé"})
    assert response.status_code == 403


def test_an_incomplete_profile_is_named_before_the_choice(client):
    sign_up_and_in(client)
    page = client.post("/companies/dev01/preview", data={
        "style": "direct", "language": "en", "showcase": "1", "company_line": "",
        "csrf": csrf(client, "/companies/dev01")}).text
    assert "Complete your profile first" in page


def test_the_supabase_store_does_not_ask_for_a_mail_that_cannot_exist():
    from tests.api.test_supabase_store import Recorder, store as supabase_store
    recorder = Recorder()
    assert supabase_store(recorder).mail("s1", "not-a-uuid") is None
    assert recorder.requests == []


# --- 6. database and container ------------------------------------------------

SQL = (ROOT / "supabase" / "migrations" / "0004_students.sql").read_text()


def test_sign_up_is_refused_when_no_code_is_set():
    trigger = SQL.split("create function check_invitation_code()", 1)[1].split("$$;", 1)[0]
    assert "v_code is null or v_code = ''" in trigger


def test_deleting_a_user_in_supabase_anonymises_their_mails():
    assert "before delete on auth.users" in SQL
    body = SQL.split("create function anonymise_student()", 1)[1].split("$$;", 1)[0]
    for column in ("student_id = null", "body = null", "person_name = null", "address = null"):
        assert column in body, column
    assert "revoke all on function anonymise_student() from public, anon, authenticated;" in SQL


def test_the_container_runs_unprivileged_with_pinned_dependencies():
    docker = (ROOT / "Dockerfile").read_text()
    assert "USER " in docker and "requirements.txt" in docker
    assert 'forwarded-allow-ips="*"' not in docker
    lock = (ROOT / "requirements.txt").read_text()
    assert "fastapi==" in lock and "supabase==" in lock and "pytest" not in lock


def test_the_supabase_profile_keeps_the_degree_level():
    from kaltstart.api.supabase_store import _PROFILE_FIELDS
    assert "degree_level" in _PROFILE_FIELDS
    assert "degree_level text check (degree_level in ('bachelor', 'master'))" in SQL


def test_the_supabase_profile_keeps_the_cv_choice():
    from kaltstart.api.supabase_store import _PROFILE_FIELDS
    assert "attach_cv" in _PROFILE_FIELDS
    assert "attach_cv boolean not null default true" in SQL
