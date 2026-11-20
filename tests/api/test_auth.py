from tests.api.conftest import CODE, csrf, sign_up_and_in


def test_sign_up_with_a_wrong_code_creates_nobody(client, auth):
    page = client.post("/signup", data={"email": "lea@example.com", "password": "a-long-password",
                                        "code": "wrong", "csrf": csrf(client, "/signup")})
    assert page.status_code == 400 and "Sign-up failed" in page.text
    assert auth.users == {}


def test_sign_up_signs_in_and_opens_the_profile(client, auth):
    response = client.post("/signup", data={"email": "lea@example.com",
                                            "password": "a-long-password", "code": CODE,
                                            "csrf": csrf(client, "/signup")})
    assert response.status_code == 303 and response.headers["location"] == "/profile"
    assert "lea@example.com" in auth.users
    assert client.get("/companies").status_code == 200        # signed in, not sent to /signin


def test_sign_up_renews_the_form_token(client):
    old = csrf(client, "/signup")
    client.post("/signup", data={"email": "lea@example.com", "password": "a-long-password",
                                 "code": CODE, "csrf": old})
    assert client.post("/signout", data={"csrf": old}).status_code == 403


def test_sign_up_never_tries_a_password_through_sign_in(client, auth):
    # Review 2026-11-20: a second sign-in call would let /signup test passwords
    # on an existing account if Supabase ever answered it with a fake success.
    def refuse(*args):
        raise AssertionError("sign-up must use the session of sign_up itself")
    auth.sign_in = refuse
    response = client.post("/signup", data={"email": "lea@example.com",
                                            "password": "a-long-password", "code": CODE,
                                            "csrf": csrf(client, "/signup")})
    assert response.status_code == 303 and response.headers["location"] == "/profile"


def test_without_a_session_from_sign_up_the_account_page_says_to_sign_in(client, auth):
    # E-mail confirmation is off in Supabase (D103); if it ever comes back,
    # sign_up gives no session and the student signs in by hand.
    auth.confirm_required = True
    page = client.post("/signup", data={"email": "lea@example.com", "password": "a-long-password",
                                        "code": CODE, "csrf": csrf(client, "/signup")})
    assert page.status_code == 200 and "Your account is ready" in page.text
    assert "sent you" not in page.text
    assert 'class="btn btn-primary" href="/signin"' in page.text
    assert "lea@example.com" in auth.users
    assert client.get("/companies").status_code == 303        # not signed in


def test_a_signed_in_student_is_not_shown_the_sign_up_form(client):
    sign_up_and_in(client)
    response = client.get("/signup")
    assert response.status_code == 303 and response.headers["location"] == "/companies"


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


def test_the_app_asks_the_store_whether_a_code_is_valid(client, store):
    from tests.api.conftest import csrf
    asked = []
    store.invitation_ok = lambda code: asked.append(code) or code == "KS-ONE"
    client.post("/signup", data={"email": "x@example.com", "password": "a-long-password",
                                 "code": "KS-ONE", "csrf": csrf(client, "/signup")})
    # Signed in by the first sign-up, so the form token is read on another page.
    wrong = client.post("/signup", data={"email": "y@example.com", "password": "a-long-password",
                                         "code": "KS-TWO", "csrf": csrf(client, "/companies")})
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
