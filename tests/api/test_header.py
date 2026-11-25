"""The signed-in header (D112, after the owner's example): the three pages in
one segmented control, and the weekly counter as a bubble with a big number."""

import re
from pathlib import Path

from tests.api.conftest import sign_up_and_in, user_id
from tests.api.test_mails import keep

CSS = (Path(__file__).parents[2] / "src/kaltstart/api/static/app.css").read_text()


def header(page):
    return page.split("<header", 1)[1].split("</header>", 1)[0]


def test_the_pages_sit_in_one_segmented_control(client):
    sign_up_and_in(client)
    nav = header(client.get("/mails").text)
    assert '<nav class="nav-links segmented" aria-label="Main">' in nav
    current = re.findall(r'<a [^>]*aria-current="page"[^>]*>([^<]+)</a>', nav)
    assert current == ["My mails"]
    assert ".segmented a[aria-current=\"page\"]" in CSS


def test_the_counter_shows_the_week_and_the_waiting_mails(client, store, auth):
    sign_up_and_in(client)
    keep(store, user_id(auth))
    top = header(client.get("/companies").text)
    assert '<b class="pill-number">1</b>' in top
    assert '<span class="pill-of">/ 10 kept this week</span>' in top
    assert '<span class="pill-waiting">1 waiting</span>' in top
    assert '<span class="pill-short">1/10 kept</span>' in top


def test_the_segmented_control_keeps_44px_targets_on_a_phone():
    phone = CSS.split("/* --- phone header", 1)[1]
    assert ".nav-signed-in .segmented a" in phone and "min-height: 44px" in phone


def test_the_current_page_is_readable_in_both_themes():
    # Review 2026-11-25: --primary text on --primary-soft was 2.3:1 in light.
    rule = CSS.split('.segmented a[aria-current="page"] {', 1)[1].split("}", 1)[0]
    assert "color: var(--link)" in rule


def test_the_counter_is_read_aloud_as_a_sentence(client):
    sign_up_and_in(client)
    top = header(client.get("/companies").text)
    assert 'aria-label="0 of 10 mails kept this week, 0 waiting"' in top
