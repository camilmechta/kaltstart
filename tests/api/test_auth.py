from tests.api.conftest import CODE, csrf, sign_up_and_in


def test_sign_up_with_a_wrong_code_creates_nobody(client, auth):
    page = client.post("/signup", data={"email": "lea@example.com", "password": "a-long-password",
                                        "code": "wrong", "csrf": csrf(client, "/signup")})
    assert page.status_code == 400 and "Sign-up failed" in page.text
    assert auth.users == {}


def test_sign_up_with_the_code_asks_to_confirm_the_email(client, auth):
    page = client.post("/signup", data={"email": "lea@example.com", "password": "a-long-password",
                                        "code": CODE, "csrf": csrf(client, "/signup")})
    assert page.status_code == 200 and "confirm" in page.text.lower()
    assert "lea@example.com" in auth.users


def test_the_eleventh_sign_up_attempt_in_an_hour_is_refused(client):
    for n in range(10):
        client.post("/signup", data={"email": f"x{n}@example.com", "password": "a-long-password",
                                     "code": "wrong", "csrf": csrf(client, "/signup")})
    page = client.post("/signup", data={"email": "y@example.com", "password": "a-long-password",
                                        "code": CODE, "csrf": csrf(client, "/signup")})
    assert page.status_code == 429


def test_sign_in_sets_the_session_and_goes_to_the_companies(client):
    response = sign_up_and_in(client)
    assert response.headers["location"] == "/companies"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie


def test_a_wrong_password_is_refused(client):
    sign_up_and_in(client)
    client.post("/signout", data={"csrf": csrf(client, "/companies")})
    page = client.post("/signin", data={"email": "lea@example.com", "password": "wrong",
                                        "csrf": csrf(client)})
    assert page.status_code == 400


def test_a_protected_page_without_a_session_goes_to_sign_in(client):
    response = client.get("/companies?country=Germany")
    assert response.status_code == 303
    assert response.headers["location"] == "/signin?next=/companies%3Fcountry%3DGermany"


def test_sign_in_returns_to_the_page_asked_for(client):
    sign_up_and_in(client)
    client.post("/signout", data={"csrf": csrf(client, "/companies")})
    response = client.post("/signin?next=/profile", data={
        "email": "lea@example.com", "password": "a-long-password", "csrf": csrf(client)})
    assert response.headers["location"] == "/profile"


def test_next_never_leaves_the_site(client):
    sign_up_and_in(client)
    client.post("/signout", data={"csrf": csrf(client, "/companies")})
    response = client.post("/signin?next=https://evil.example.com", data={
        "email": "lea@example.com", "password": "a-long-password", "csrf": csrf(client)})
    assert response.headers["location"] == "/companies"


def test_a_post_without_the_right_csrf_token_is_refused(client, auth):
    for token in (None, "wrong"):
        data = {"email": "lea@example.com", "password": "a-long-password", "code": CODE}
        if token:
            data["csrf"] = token
        assert client.post("/signup", data=data).status_code == 403
    assert auth.users == {}


def test_sign_out_ends_the_session(client):
    sign_up_and_in(client)
    client.post("/signout", data={"csrf": csrf(client, "/companies")})
    assert client.get("/companies").status_code == 303


def test_sign_in_and_sign_up_titles_match_and_help_is_given(client):
    signin, signup = client.get("/signin").text, client.get("/signup").text
    assert 'class="title-xl"' in signin and 'class="title-xl"' in signup
    assert "At least 8 characters" in signup
    assert "The code you were invited with." in signup


def test_a_failed_sign_in_keeps_the_email(client):
    from tests.api.conftest import csrf
    page = client.post("/signin", data={"email": "nobody@example.com", "password": "wrongpass1",
                                        "csrf": csrf(client, "/signin")}).text
    assert 'value="nobody@example.com"' in page


def test_after_sign_up_a_sign_in_button_is_shown(client):
    from tests.api.conftest import csrf
    page = client.post("/signup", data={"email": "new@example.com", "password": "longenough1",
                                        "code": "dev", "csrf": csrf(client, "/signup")}).text
    assert 'class="btn btn-primary" href="/signin"' in page


def test_the_app_asks_the_store_whether_a_code_is_valid(client, store):
    from tests.api.conftest import csrf
    asked = []
    store.invitation_ok = lambda code: asked.append(code) or code == "KS-ONE"
    client.post("/signup", data={"email": "x@example.com", "password": "a-long-password",
                                 "code": "KS-ONE", "csrf": csrf(client, "/signup")})
    wrong = client.post("/signup", data={"email": "y@example.com", "password": "a-long-password",
                                         "code": "KS-TWO", "csrf": csrf(client, "/signup")})
    assert asked == ["KS-ONE", "KS-TWO"] and wrong.status_code == 400


# A second click on "Sign in" (the friend's report, 2026-11-19): the first one
# signed in and changed the form token, the second sent the old one.
def test_a_second_click_on_sign_in_goes_to_the_companies(client):
    from tests.api.conftest import CODE, csrf
    client.post("/signup", data={"email": "lea@example.com", "password": "a-long-password",
                                 "code": CODE, "csrf": csrf(client, "/signup")})
    data = {"email": "lea@example.com", "password": "a-long-password", "csrf": csrf(client)}
    assert client.post("/signin", data=data).status_code == 303
    again = client.post("/signin", data=data)
    assert again.status_code == 303 and again.headers["location"] == "/companies"


def test_a_stale_sign_in_form_is_still_refused_when_signed_out(client):
    from tests.api.conftest import csrf
    csrf(client)
    response = client.post("/signin", data={"email": "lea@example.com",
                                            "password": "a-long-password", "csrf": "stale"})
    assert response.status_code == 403


def test_sign_in_and_sign_up_buttons_are_sent_once(client):
    from pathlib import Path
    for path in ("/signin", "/signup"):
        assert "data-submit-once" in client.get(path).text, path
    script = (Path(__file__).parents[2] / "src" / "kaltstart" / "api" / "static" / "app.js").read_text()
    assert "data-submit-once" in script
