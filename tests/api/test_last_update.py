"""The "Updated" bubble of the company list (D111): when the nightly job last
brought the funding rounds up to date, read from its own run log."""

from datetime import datetime, timedelta, timezone

import pytest

from kaltstart.api.pages import updated_label
from tests.api.conftest import NOW, sign_up_and_in

# NOW is 2026-11-16 12:00 UTC, 13:00 in Zurich.


@pytest.mark.parametrize("at,expected", [
    (datetime(2026, 11, 16, 3, 12, tzinfo=timezone.utc), "Updated today, 04:12"),
    (datetime(2026, 11, 15, 3, 12, tzinfo=timezone.utc), "Updated yesterday, 04:12"),
    (datetime(2026, 11, 13, 3, 12, tzinfo=timezone.utc), "Updated 13 Nov, 04:12"),
    (datetime(2026, 11, 15, 23, 30, tzinfo=timezone.utc), "Updated today, 00:30"),   # Zurich day
    (datetime(2026, 7, 15, 3, 12, tzinfo=timezone.utc), "Updated 15 Jul, 05:12"),    # summer time
])
def test_the_label_is_in_swiss_time(at, expected):
    assert updated_label(at, NOW) == expected


def test_no_label_without_a_run():
    assert updated_label(None, NOW) is None


def test_the_company_list_shows_when_it_was_updated(client, store):
    store.set_last_update(NOW - timedelta(hours=8, minutes=48))
    sign_up_and_in(client)
    page = client.get("/companies").text
    assert 'class="updated-pill"' in page
    assert "Updated today, 04:12" in page
    assert "New funding rounds from Tech.eu are added every night." in page


def test_no_bubble_when_no_run_is_known(client, store):
    store.set_last_update(None)
    sign_up_and_in(client)
    assert 'class="updated-pill"' not in client.get("/companies").text


def test_the_list_still_shows_when_the_update_time_cannot_be_read(client, store):
    # Review 2026-11-25: the bubble must never break the list.
    def fail():
        raise RuntimeError("database unavailable")
    store.last_update = fail
    sign_up_and_in(client)
    page = client.get("/companies")
    assert page.status_code == 200 and 'class="updated-pill"' not in page.text
