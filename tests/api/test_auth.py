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
