"""Clear sign-in errors and the password reset (design 2026-11-19)."""

import pytest

from kaltstart.api.auth import SupabaseAuth, sign_in_reason
from tests.api.conftest import CODE, csrf, sign_up_and_in

EMAIL, OLD, NEW = "lea@example.com", "a-long-password", "a-new-long-password"


def signed_up(client):
    client.post("/signup", data={"email": EMAIL, "password": OLD, "code": CODE,
                                 "csrf": csrf(client, "/signup")})


def sign_in(client, password=OLD, email=EMAIL):
    return client.post("/signin", data={"email": email, "password": password,
                                        "csrf": csrf(client)})


# --- sign-in errors ---------------------------------------------------------

def error(status, code):
    from supabase_auth.errors import AuthApiError
    return AuthApiError("message from Supabase", status, code)


@pytest.mark.parametrize("exc,reason", [
    (error(400, "invalid_credentials"), "credentials"),
    (error(400, "email_not_confirmed"), "unconfirmed"),
    (error(429, "over_request_rate_limit"), "busy"),
    (error(500, "unexpected_failure"), "unavailable"),
    (ConnectionError("down"), "unavailable"),
])
def test_supabase_errors_become_reasons(exc, reason):
    assert sign_in_reason(exc) == reason


@pytest.mark.parametrize("reason,message", [
    ("credentials", "Wrong e-mail or password."),
    ("unconfirmed", "Confirm your e-mail address first: open the link we sent you."),
    ("busy", "Too many sign-ins right now. Try again in a few minutes."),
    ("unavailable", "Sign-in is not working right now. Try again in a moment."),
])
def test_each_sign_in_failure_has_its_message(client, auth, reason, message):
    signed_up(client)
    auth.fail_sign_in_with = None if reason == "credentials" else reason
    page = sign_in(client, password="wrong-password" if reason == "credentials" else OLD)
    assert page.status_code in (400, 429, 503) and message in page.text


def test_the_sign_in_page_links_to_the_reset(client):
    assert 'href="/forgot-password"' in client.get("/signin").text


# --- forgot password --------------------------------------------------------

def forgot(client, email):
    return client.post("/forgot-password", data={"email": email,
                                                 "csrf": csrf(client, "/forgot-password")})


def test_the_answer_does_not_tell_whether_an_account_exists(client, auth):
    signed_up(client)
    known, unknown = forgot(client, EMAIL), forgot(client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 200
    message = "If an account uses this address, we sent a link to choose a new password."
    assert message in known.text and message in unknown.text
    assert list(auth.reset_tokens.values()) == [EMAIL]


def test_forgot_password_needs_the_form_token(client):
    response = client.post("/forgot-password", data={"email": EMAIL, "csrf": "stale"})
    assert response.status_code == 403


def test_forgot_password_is_rate_limited(client, auth):
    for _ in range(10):
        forgot(client, EMAIL)
    assert forgot(client, EMAIL).status_code == 429


# --- reset ------------------------------------------------------------------

def reset(client, token, password=NEW, again=None):
    page = client.get(f"/reset-password?token_hash={token}")
    marker = 'name="csrf" value="'
    token_csrf = page.text.split(marker, 1)[1].split('"', 1)[0]
    return client.post("/reset-password", data={
        "token_hash": token, "password": password, "password_again": again or password,
        "csrf": token_csrf})


def test_opening_the_link_does_not_spend_it(client, auth):
    signed_up(client)
    forgot(client, EMAIL)
    token = next(iter(auth.reset_tokens))
    assert client.get(f"/reset-password?token_hash={token}").status_code == 200
    assert token in auth.reset_tokens


def test_a_good_link_changes_the_password(client, auth):
    signed_up(client)
    forgot(client, EMAIL)
    response = reset(client, next(iter(auth.reset_tokens)))
    assert response.status_code == 303 and response.headers["location"] == "/signin?reset=1"
    assert "Your password is changed. Sign in with the new one." in client.get("/signin?reset=1").text
    assert sign_in(client, password=OLD).status_code == 400
    assert sign_in(client, password=NEW).status_code == 303


def test_a_spent_link_is_refused(client, auth):
    signed_up(client)
    forgot(client, EMAIL)
    token = next(iter(auth.reset_tokens))
    reset(client, token)
    page = reset(client, token, password="another-long-password")
    assert page.status_code == 400 and "This link has expired." in page.text
    assert page.text.count("Ask for a new") == 1 and 'href="/forgot-password"' in page.text


@pytest.mark.parametrize("password,again,message", [
    (NEW, "something-else-entirely", "The two passwords are not the same."),
    ("short", "short", "at least 8 characters"),
])
def test_a_bad_new_password_keeps_the_form(client, auth, password, again, message):
    signed_up(client)
    forgot(client, EMAIL)
    token = next(iter(auth.reset_tokens))
    page = reset(client, token, password=password, again=again)
    assert page.status_code == 400 and message in page.text
    assert token in auth.reset_tokens


@pytest.mark.parametrize("path,label", [
    ("/signin", "Signing in…"), ("/signup", "Creating your account…"),
    ("/forgot-password", "Sending…"), ("/reset-password?token_hash=x", "Changing…")])
def test_each_sent_once_button_says_what_it_is_doing(client, path, label):
    assert f'data-sending="{label}"' in client.get(path).text



# --- final review of the reset (2026-11-19) -----------------------------------

def test_a_refused_new_password_says_the_link_is_used(client, auth):
    signed_up(client)
    forgot(client, EMAIL)
    auth.refused_passwords.add(NEW)
    page = reset(client, next(iter(auth.reset_tokens)))
    assert page.status_code == 400
    assert "This password was refused: it is too weak or the same as before." in page.text
    assert "The link is now used" in page.text and 'href="/forgot-password"' in page.text
    assert 'name="password"' not in page.text


def test_reset_attempts_are_rate_limited(client):
    for _ in range(10):
        reset(client, "guess")
    assert reset(client, "guess").status_code == 429


class _Raising:
    """A Supabase client whose verify_otp raises the given error."""
    def __init__(self, exc):
        self.auth = self
        self._exc = exc

    def verify_otp(self, params):
        raise self._exc


@pytest.mark.parametrize("exc,result", [
    (error(403, "otp_expired"), "expired"),
    (error(429, "over_request_rate_limit"), "unavailable"),
    (error(500, "unexpected_failure"), "unavailable"),
    (ConnectionError("down"), "unavailable"),
])
def test_supabase_reset_errors(exc, result, monkeypatch):
    real = SupabaseAuth("https://example.supabase.co", "anon", "service")
    monkeypatch.setattr(real, "_client", lambda key: _Raising(exc))
    assert real.reset_password("hash", NEW) == result


# --- the default Supabase link (2026-11-19): templates cannot be edited without
# a custom SMTP, so the e-mail keeps Supabase's own link. Supabase checks the
# token, then sends the student to the site with a recovery session in the URL
# fragment; a script puts it in the form.

def session_reset(client, access, refresh="r", password=NEW, again=None):
    page = client.get("/reset-password")
    marker = 'name="csrf" value="'
    token_csrf = page.text.split(marker, 1)[1].split('"', 1)[0]
    return client.post("/reset-password", data={
        "access_token": access, "refresh_token": refresh, "password": password,
        "password_again": again or password, "csrf": token_csrf})


def test_the_reset_page_has_fields_for_the_recovery_session(client):
    page = client.get("/reset-password").text
    assert 'name="access_token"' in page and 'name="refresh_token"' in page
    assert "data-recovery" in page


def test_a_recovery_session_changes_the_password(client, auth):
    signed_up(client)
    forgot(client, EMAIL)
    response = session_reset(client, next(iter(auth.reset_tokens)))
    assert response.status_code == 303 and response.headers["location"] == "/signin?reset=1"
    assert sign_in(client, password=NEW).status_code == 303


def test_a_wrong_recovery_session_is_refused(client, auth):
    signed_up(client)
    page = session_reset(client, "not-a-session")
    assert page.status_code == 400 and "This link has expired." in page.text


def test_an_expired_link_from_supabase_shows_the_spent_page(client):
    page = client.get("/reset-password?expired=1").text
    assert "This link has expired." in page and 'name="password"' not in page


def test_the_script_sends_a_recovery_fragment_to_the_reset_page():
    from pathlib import Path
    script = (Path(__file__).parents[2] / "src" / "kaltstart" / "api" / "static" / "app.js").read_text()
    for words in ('params.get("type") === "recovery"', "/reset-password", "history.replaceState",
                  "access_token"):
        assert words in script, words
