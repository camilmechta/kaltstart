from datetime import timedelta

import pytest

from kaltstart.api.store import NewMail
from tests.api.conftest import NOW, csrf, sign_up_and_in, user_id


def keep(store, student, company="dev01", days=0.0, subject="Nova Learn internship?"):
    return store.reserve(student, NewMail(
        company_id=company, round_id="round01", address="info@novalearn.example.de",
        address_type="generic", person_name="Anna Muster", person_key=None,
        person_choice="suggested", person_source_url="https://novalearn.example.de/team",
        style="direct", language="en", company_line=None, used_company_line=False,
        subject=subject, body="Hi Anna!\n\nCongrats on your round."), NOW - timedelta(days=days))


def status(client, mail_id, value):
    return client.post(f"/mails/{mail_id}/status",
                       data={"status": value, "csrf": csrf(client, "/mails")})


def test_my_mails_lists_the_students_mails_newest_first(client, store, auth):
    sign_up_and_in(client)
    me = user_id(auth)
    keep(store, me, "dev01", days=2, subject="First?")
    keep(store, me, "dev02", days=1, subject="Second?")
    page = client.get("/mails").text
    assert page.index("Second?") < page.index("First?")
    assert "2 of 5 mails in progress" in page


def test_another_students_mails_are_not_listed_nor_reachable(client, store, auth):
    other = keep(store, "someone-else", "dev03", subject="Not yours?")
    sign_up_and_in(client)
    assert "Not yours?" not in client.get("/mails").text
    assert client.get(f"/mails/{other}").status_code == 404
    assert status(client, other, "sent").status_code == 404


def test_the_reminder_between_72_hours_and_7_days(client, store, auth):
    sign_up_and_in(client)
    keep(store, user_id(auth), "dev01", days=4)
    assert "did you send it" in client.get("/mails").text.lower()


def test_presumed_sent_after_7_days(client, store, auth):
    sign_up_and_in(client)
    keep(store, user_id(auth), "dev01", days=8)
    page = client.get("/mails").text
    assert "Presumed sent" in page and "did you send it" not in page.lower()


def test_a_mail_page_shows_the_copy_buttons(client, store, auth):
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    page = client.get(f"/mails/{mail_id}").text
    assert page.count("data-copy=") == 3
    assert "info@novalearn.example.de" in page and "Congrats on your round." in page


@pytest.mark.parametrize("path,expected", [
    (["sent"], "sent"), (["sent", "human_reply", "positive_reply"], "positive_reply"),
    (["abandoned"], "abandoned"), (["sent", "copied"], "sent"),
    (["sent", "abandoned"], "sent"), (["positive_reply", "sent"], "positive_reply"),
])
def test_statuses_only_move_forward(client, store, auth, path, expected):
    sign_up_and_in(client)
    me = user_id(auth)
    mail_id = keep(store, me)
    for value in path:
        status(client, mail_id, value)
    assert store.mail(me, mail_id).status == expected


def test_copying_the_body_marks_the_mail_copied(client, store, auth):
    sign_up_and_in(client)
    me = user_id(auth)
    mail_id = keep(store, me)
    response = client.post(f"/mails/{mail_id}/copied", data={"csrf": csrf(client, "/mails")})
    assert response.status_code == 204
    assert store.mail(me, mail_id).status == "copied"


def test_a_kept_mail_says_kept_and_confirms_it(client, store, auth):
    sign_up_and_in(client)
    mail = keep(store, user_id(auth))
    listing = client.get("/mails").text
    assert "Kept" in listing and ">Generated<" not in listing
    assert 'class="status-pill' in listing and 'class="row' in listing
    page = client.get(f"/mails/{mail}?kept=1").text
    assert "Kept. Copy it and send it from your own mailbox." in page
    assert 'class="kicker"' in listing
