import pytest

from kaltstart.mailgen.models import ROLES
from tests.api.conftest import PROFILE, csrf, save_profile, sign_up_and_in, user_id


def test_the_profile_form_has_every_field(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    for name in ("first_name", "last_name", "programme", "lang_en", "lang_de", "target_role",
                 "request", "start_date", "duration_months", "workload_percent", "link",
                 "showcase1_en", "showcase1_de", "showcase2_en", "showcase2_de", "pref_country"):
        assert f'name="{name}"' in page, name
    for role in ROLES:
        assert f'value="{role}"' in page
    assert 'data-max-words="60"' in page


def test_saving_the_profile(client, store, auth):
    sign_up_and_in(client)
    response = save_profile(client)
    assert response.status_code == 303 and response.headers["location"] == "/profile?saved=1"
    profile = store.profile(user_id(auth))
    assert (profile.first_name, profile.target_role, profile.duration_months) == ("Lea", "growth", 3)
    assert profile.preferred_countries == ("Switzerland", "Germany")
    assert store.showcases(user_id(auth))[0].text_en == PROFILE["showcase1_en"]
    assert "Lea" in client.get("/profile?saved=1").text


@pytest.mark.parametrize("changes,message", [
    (dict(showcase1_en=""), "Showcase sentence 1"),
    (dict(lang_de="on"), "German version"),
    (dict(showcase1_en=" ".join(["word"] * 61)), "60 words"),
    (dict(programme="x" * 71), "70 characters"),
    (dict(first_name=""), "First name"),
    (dict(target_role="design"), "Target role"),
    (dict(link="not a link"), "Link"),
    (dict(request="part_time", workload_percent=""), "Workload"),
])
def test_invalid_profiles_are_refused_with_the_field_named(client, store, auth, changes, message):
    sign_up_and_in(client)
    page = save_profile(client, **changes)
    assert page.status_code == 400 and message in page.text
    assert store.profile(user_id(auth)) is None


def test_german_version_is_kept_when_german_is_ticked(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, lang_de="on", showcase1_de="Ich habe einen Newsletter aufgebaut.")
    assert store.profile(user_id(auth)).languages == ("en", "de")
    assert store.showcases(user_id(auth))[0].text_de == "Ich habe einen Newsletter aufgebaut."


def test_deleting_the_account(client, store, auth):
    sign_up_and_in(client)
    save_profile(client)
    student = user_id(auth)
    assert "cannot be undone" in client.get("/profile/delete").text
    response = client.post("/profile/delete", data={"csrf": csrf(client, "/profile/delete")})
    assert response.status_code == 303 and response.headers["location"] == "/signin?deleted=1"
    assert store.profile(student) is None and auth.users == {}
    assert client.get("/profile").status_code == 303


def test_a_profile_belongs_to_its_student(client, store, auth):
    sign_up_and_in(client)
    save_profile(client)
    client.post("/signout", data={"csrf": csrf(client, "/profile")})
    sign_up_and_in(client, email="other@example.com")
    assert "Beispiel" not in client.get("/profile").text
