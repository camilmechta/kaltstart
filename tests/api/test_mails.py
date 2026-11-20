import html
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
    assert "2 of 10 mails kept this week · 2 waiting" in page


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


def test_the_status_buttons_carry_the_page_token(client, store, auth):
    """The buttons are posted as the browser does, with the token the page holds."""
    import re
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    for path in ("/mails", f"/mails/{mail_id}"):
        page = client.get(path).text
        form = page.split(f'action="/mails/{mail_id}/status"', 1)[1].split("</form>", 1)[0]
        token = re.search(r'name="csrf" value="([^"]*)"', form).group(1)
        assert token, path
        response = client.post(f"/mails/{mail_id}/status",
                                data={"csrf": token, "status": "sent", "back": path})
        assert response.status_code == 303, path


def test_a_refusal_is_a_page_not_a_download(client):
    response = client.post("/signin", data={"email": "a@example.com", "password": "x"})
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("text/html")
    sign_up_and_in(client)
    missing = client.get("/mails/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404 and missing.headers["content-type"].startswith("text/html")


def test_the_mail_page_reminds_to_attach_the_cv(client, store, auth):
    from tests.api.conftest import save_profile
    sign_up_and_in(client)
    save_profile(client, attach_cv="on")
    mail_id = keep(store, user_id(auth))
    assert "Attach your CV before you send it." in client.get(f"/mails/{mail_id}").text
    save_profile(client)
    assert "Attach your CV" not in client.get(f"/mails/{mail_id}").text


# --- Did they reply? (design 2026-11-20) -----------------------------------------

def sent(store, me, company="dev01", days=15):
    mail_id = keep(store, me, company, days=days + 1)
    store.set_status(me, mail_id, "sent", NOW - timedelta(days=days))
    return mail_id


def test_a_sent_mail_can_be_marked_no_reply_then_still_get_a_reply(client, store, auth):
    sign_up_and_in(client)
    me = user_id(auth)
    mail_id = sent(store, me)
    assert "No reply yet" in client.get(f"/mails/{mail_id}").text
    status(client, mail_id, "no_reply")
    assert store.mail(me, mail_id).status == "no_reply"
    page = client.get(f"/mails/{mail_id}").text
    assert 'status-pill status-no_reply">No reply<' in page
    assert "No reply yet" not in page and "Got a reply" in page
    status(client, mail_id, "human_reply")
    assert store.mail(me, mail_id).status == "human_reply"


def test_a_reply_cannot_go_back_to_no_reply(client, store, auth):
    sign_up_and_in(client)
    me = user_id(auth)
    mail_id = sent(store, me)
    status(client, mail_id, "human_reply")
    status(client, mail_id, "no_reply")
    assert store.mail(me, mail_id).status == "human_reply"


def test_no_reply_is_not_offered_before_sending(client, store, auth):
    sign_up_and_in(client)
    me = user_id(auth)
    mail_id = keep(store, me)
    status(client, mail_id, "no_reply")
    assert store.mail(me, mail_id).status == "generated"


def test_my_mails_asks_about_a_mail_sent_14_days_ago_or_more(client, store, auth):
    sign_up_and_in(client)
    me = user_id(auth)
    old = sent(store, me, "dev01", days=15)
    sent(store, me, "dev02", days=3)
    page = html.unescape(client.get("/mails").text)
    assert page.count("did they reply?") == 1
    assert "was sent 15 days ago: did they reply?" in page
    notice = page.split("did they reply?")[1].split("</div>\n</div>")[0]
    assert "Got a reply" in notice and "Positive reply" in notice and "No reply yet" in notice
    status(client, old, "no_reply")
    assert "did they reply?" not in client.get("/mails").text


def test_another_students_old_sent_mail_asks_nothing(client, store, auth):
    sent(store, "someone-else", "dev01", days=20)
    sign_up_and_in(client)
    assert "did they reply?" not in client.get("/mails").text
    assert "did they reply?" not in client.get("/companies").text


def test_the_company_list_points_to_the_mails_to_check(client, store, auth):
    sign_up_and_in(client)
    me = user_id(auth)
    sent(store, me, "dev01", days=15)
    page = client.get("/companies").text
    assert "1 mail sent 2 weeks ago or more: did they reply?" in page
    assert 'class="progress-strip progress-check"' in page
    sent(store, me, "dev02", days=20)
    page = client.get("/companies").text
    assert "2 mails sent 2 weeks ago or more: did they reply?" in page
    assert 'href="/mails"' in page.split("2 mails sent 2 weeks ago")[0].rsplit("<a", 1)[1]


def test_a_recent_sent_mail_adds_no_line_to_the_company_list(client, store, auth):
    sign_up_and_in(client)
    sent(store, user_id(auth), "dev01", days=3)
    assert "did they reply?" not in client.get("/companies").text
