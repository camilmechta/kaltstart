"""Fixes after an outside review (2026-11-17): atomic profile save, removal
in kept mails, one read of company names on My mails (D87)."""

import json

import pytest

from kaltstart.api.store import InMemoryAppStore, Profile, Showcase
from tests.api.conftest import NOW, csrf, save_profile, sign_up_and_in, user_id
from tests.api.test_mails import keep


# --- 1. the profile and its showcases in one step ------------------------------

def test_the_in_memory_store_saves_profile_and_showcases_together():
    store = InMemoryAppStore(invitation="dev")
    store.save_profile(Profile(id="s1", first_name="Lea"),
                       [Showcase(1, "One.", None), Showcase(2, "Two.", None)])
    store.save_profile(Profile(id="s1", first_name="Lea"), [Showcase(1, "One again.", None)])
    assert [s.text_en for s in store.showcases("s1")] == ["One again."]


def test_a_failed_save_keeps_the_previous_profile_and_showcases():
    store = InMemoryAppStore(invitation="dev")
    store.save_profile(Profile(id="s1", first_name="Lea"), [Showcase(1, "One.", None)])
    with pytest.raises(ValueError):
        store.save_profile(Profile(id="s1", first_name="Changed"), [Showcase(3, "Bad.", None)])
    assert store.profile("s1").first_name == "Lea"
    assert [s.text_en for s in store.showcases("s1")] == ["One."]


def test_the_supabase_store_saves_in_one_database_call():
    from tests.api.test_supabase_store import Recorder, store as supabase_store
    recorder = Recorder(rpc=None)
    supabase_store(recorder).save_profile(Profile(id="s1", first_name="Lea"),
                                          [Showcase(1, "One.", None)])
    assert len(recorder.requests) == 1
    request = recorder.requests[0]
    assert request.url.path.endswith("/rpc/save_profile_and_showcases")
    body = json.loads(request.content)
    assert body["p_student_id"] == "s1" and body["p_profile"]["first_name"] == "Lea"
    assert body["p_showcases"] == [{"position": 1, "text_en": "One.", "text_de": None}]


def test_the_profile_page_says_nothing_changed_when_saving_fails(client, store, auth):
    sign_up_and_in(client)
    save_profile(client)
    before = store.profile(user_id(auth))

    def broken(profile, showcases):
        raise RuntimeError("database unavailable")
    store.save_profile = broken
    response = save_profile(client, first_name="Changed")
    assert response.status_code == 503
    assert "Your profile could not be saved. Nothing was changed." in response.text
    assert store.profile(user_id(auth)) == before


# --- 2. a kept mail cleared after a removal on request -------------------------

def test_a_cleared_mail_shows_a_clear_state_and_nothing_to_copy(client, store, auth):
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    store.redact_company("dev01")
    page = client.get(f"/mails/{mail_id}").text
    assert "Removed on request" in page and "None" not in page
    assert "data-copy=" not in page
    assert "cannot remove a copy you already pasted" in page
    listing = client.get("/mails").text
    assert "Removed on request" in listing and "None" not in listing


def test_a_cleared_mail_cannot_be_marked_copied_but_can_still_be_tracked(client, store, auth):
    sign_up_and_in(client)
    mail_id = keep(store, user_id(auth))
    store.redact_company("dev01")
    token = csrf(client, "/mails")
    assert client.post(f"/mails/{mail_id}/copied", data={"csrf": token}).status_code == 204
    assert store.mail(user_id(auth), mail_id).status == "generated"
    client.post(f"/mails/{mail_id}/status", data={"csrf": token, "status": "abandoned",
                                                   "back": "/mails"})
    assert store.mail(user_id(auth), mail_id).status == "abandoned"


def test_another_persons_mail_is_left_alone(store, auth, client):
    sign_up_and_in(client)
    mine = keep(store, user_id(auth), "dev01")
    other = keep(store, user_id(auth), "dev02")
    store.redact_company("dev01")
    assert store.mail(user_id(auth), mine).body is None
    assert store.mail(user_id(auth), other).body == "Hi Anna!\n\nCongrats on your round."


# --- 3. one read of company names for My mails ---------------------------------

def test_my_mails_reads_company_names_once(store, auth):
    from tests.api.test_hardening import CountingStore, make_client
    counting = CountingStore(store)
    client = make_client(counting, auth)
    sign_up_and_in(client)
    for company in ("dev01", "dev02", "dev03", "dev04", "dev05"):
        keep(store, user_id(auth), company)
    counting.calls.clear()
    client.get("/mails")
    assert counting.calls.get("company", 0) == 0 and counting.calls.get("company_names") == 1
    mail_id = store.mails(user_id(auth))[0].id
    counting.calls.clear()
    client.get(f"/mails/{mail_id}")
    assert counting.calls.get("company", 0) == 0 and counting.calls.get("company_names") == 1


def test_company_names_are_deduplicated_and_keep_old_companies(store):
    store.exclude_company("dev01")                 # no longer listed, still in the history
    names = store.company_names(["dev01", "dev01", "missing"])
    assert names["dev01"] == store._companies["dev01"].name
    assert "missing" not in names and store.company_names([]) == {}


def test_the_supabase_store_reads_names_in_one_request():
    from tests.api.test_supabase_store import Recorder, param, store as supabase_store
    recorder = Recorder(tables={"companies": [{"id": "c1", "name": "Example One"}]})
    names = supabase_store(recorder).company_names(["c1", "c1", "c2"])
    assert names == {"c1": "Example One"}
    requests = recorder.of("GET", "companies")
    assert len(requests) == 1 and param(requests[0], "id") in ("in.(c1,c2)", "in.(c2,c1)")
    empty = Recorder()
    assert supabase_store(empty).company_names([]) == {} and empty.requests == []


def test_a_mail_of_a_company_that_no_longer_exists_has_a_label(client, store, auth):
    sign_up_and_in(client)
    keep(store, user_id(auth), "dev01")
    del store._companies["dev01"]
    assert "A company no longer listed" in client.get("/mails").text
