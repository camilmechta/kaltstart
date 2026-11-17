import pytest

from kaltstart.mailgen.models import ROLES
from tests.api.conftest import PROFILE, csrf, save_profile, sign_up_and_in, user_id


def test_the_profile_form_has_every_field(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    for name in ("first_name", "last_name", "programme", "lang_de", "target_role",
                 "request", "start_date", "duration_months", "workload_percent", "link",
                 "showcase1_en", "showcase1_de", "showcase2_en", "showcase2_de", "pref_country"):
        assert f'name="{name}"' in page, name
    for role in ROLES:
        assert f'value="{role}"' in page
    assert 'data-max-words="60"' in page


def test_saving_the_profile(client, store, auth):
    sign_up_and_in(client)
    response = save_profile(client)
    assert response.status_code == 303 and response.headers["location"] == "/companies?saved=1"
    profile = store.profile(user_id(auth))
    assert (profile.first_name, profile.target_role, profile.duration_months) == ("Lea", "growth", 3)
    assert profile.preferred_countries == ("Switzerland", "Germany")
    assert store.showcases(user_id(auth))[0].text_en == PROFILE["showcase1_en"]
    assert "Lea" in client.get("/profile").text


def test_after_saving_the_student_lands_on_the_companies(client, store, auth):
    sign_up_and_in(client)
    save_profile(client)
    page = client.get("/companies?saved=1").text
    assert "Profile saved. Now pick a company to write to." in page
    # The preferences still pre-set the filters on this first view.
    assert '<option value="Switzerland" selected>' in page


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



def test_languages_are_one_clear_switch(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    assert "Every mail can be in English" in page and "I can also write in German" in page
    assert "disabled" not in page


@pytest.mark.parametrize("role,hint", [("product", "Roadmap"), ("growth", "Marketing"),
                                       ("data", "Dashboards"), ("operations", "Processes"),
                                       ("business_development", "Partners")])
def test_target_roles_are_cards(client, role, hint):
    sign_up_and_in(client)
    page = client.get("/profile").text
    assert f'type="radio" name="target_role" value="{role}"' in page
    assert hint in page and 'class="role-card' in page


def test_showcase_is_guided_and_the_rest_is_tucked_away(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    assert "What have you done that shows you can help a startup?" in page
    assert 'placeholder="e.g.' in page
    assert page.count('data-show-when="lang_de"') == 2
    second = page.split("<details", 1)[1].split("</details>", 1)[0]
    assert 'name="showcase2_en"' in second and "Add a second one" in second


def test_preferences_are_chips(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    assert page.count('class="chip-toggle"') >= 3 + 8      # three countries and the sectors


def test_a_second_showcase_opens_by_itself_when_filled(client, store, auth):
    sign_up_and_in(client)
    save_profile(client, showcase2_en="I ran the finance club's events for a year.")
    assert "<details open" in client.get("/profile").text


def test_dates_follow_the_kind_of_request(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    assert 'data-show-when="request=internship"' in page
    assert 'data-show-when="request=part_time" hidden' in page


def test_the_degree_is_bachelor_or_master_then_the_programme(client, store, auth):
    sign_up_and_in(client)
    page = client.get("/profile").text
    for level in ("bachelor", "master"):
        assert f'name="degree_level" value="{level}"' in page
    assert 'placeholder="e.g. Business Innovation"' in page
    assert 'data-show-when="degree_level=master"' in page and "Master in" in page
    response = save_profile(client, degree_level="")
    assert response.status_code == 400 and "Choose Bachelor or Master." in response.text
    save_profile(client, degree_level="bachelor")
    assert store.profile(user_id(auth)).degree_level == "bachelor"


def test_the_profile_says_why_it_asks(client):
    sign_up_and_in(client)
    page = client.get("/profile").text
    for words in ("Only you see this page.",
                  "Your name and degree sign every mail",
                  "added at the end of your mails",
                  "decides whom we suggest at each company",
                  "so the company knows when you are free"):
        assert words in page, words
