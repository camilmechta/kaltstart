import logging

from tests.api.conftest import csrf, save_profile, sign_up_and_in
from tests.api.test_company_page import client, post, store  # noqa: F401  (fixtures)

SECRETS = ("Anna Muster", "anna.muster@c1.example.ch", "Lea", "Beispiel",
           "newsletter", "lea@example.com")


def test_a_full_journey_logs_no_personal_data(client, caplog):
    caplog.set_level(logging.DEBUG)
    sign_up_and_in(client)
    save_profile(client)
    post(client, "preview", choice="suggested")
    kept = post(client, "keep", choice="suggested").headers["location"].split("?")[0]
    client.get(kept)
    client.post(kept + "/status", data={"status": "sent", "csrf": csrf(client, "/mails")})
    text = "\n".join(r.getMessage() for r in caplog.records)
    for secret in SECRETS:
        assert secret not in text, secret


def test_an_error_logs_the_route_and_the_class_only(client, caplog, store):
    sign_up_and_in(client)

    def broken(*args, **kwargs):
        raise ValueError("Anna Muster anna.muster@c1.example.ch")
    store.companies = broken
    caplog.set_level(logging.ERROR, logger="kaltstart.api")
    response = client.get("/companies")
    assert response.status_code == 500 and "Something went wrong" in response.text
    text = "\n".join(r.getMessage() + (r.exc_text or "") for r in caplog.records)
    assert "/companies" in text and "ValueError" in text
    assert "Anna" not in text and "@" not in text
