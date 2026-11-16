import re
from pathlib import Path

from tests.api.conftest import REMOVAL, sign_up_and_in

CSS = (Path(__file__).parents[2] / "src" / "kaltstart" / "api" / "static" / "app.css")
DESIGN = (Path(__file__).parents[2] / "DESIGN.md").read_text()


def test_every_page_has_the_frame(client):
    sign_up_and_in(client)
    for path in ("/companies", "/signin"):
        page = client.get(path).text
        assert '<meta name="viewport"' in page
        assert "/static/app.css" in page and "/static/app.js" in page
        assert REMOVAL in page
        assert 'data-theme-toggle' in page


def test_the_navigation_once_signed_in(client):
    sign_up_and_in(client)
    page = client.get("/companies").text
    for link in ('href="/companies"', 'href="/mails"', 'href="/profile"'):
        assert link in page
    assert "0 / 5 pending" in page


def test_the_css_defines_every_design_token_in_both_themes():
    css = CSS.read_text()
    tokens = set(re.findall(r"`(--[a-z0-9-]+)`", DESIGN))
    assert {"--bg", "--primary", "--text-base", "--space-4", "--radius-lg"} <= tokens
    for token in tokens:
        assert f"{token}:" in css, token
    for colour in ("--bg", "--surface", "--text", "--muted", "--link"):
        assert len(re.findall(rf"{colour}:", css)) >= 2, colour   # dark and light
    assert "prefers-color-scheme: light" in css and '[data-theme="light"]' in css


def test_static_files_are_served(client):
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_the_fonts_are_served_with_their_licence(client):
    for name in ("Geist-Variable.woff2", "GeistMono-Variable.woff2"):
        response = client.get(f"/static/fonts/{name}")
        assert response.status_code == 200 and response.content[:4] == b"wOF2", name
    assert "SIL Open Font License" in client.get("/static/fonts/OFL.txt").text
