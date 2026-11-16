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
    assert '<a class="pill" href="/mails"' in page and "0 of 5 mails in progress" in page


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


def test_assets_carry_a_version_so_browsers_reload_them(client):
    import hashlib
    page = client.get("/signin").text
    digest = hashlib.sha256(CSS.read_bytes()).hexdigest()[:10]
    assert f"/static/app.css?v={digest}" in page
    assert "/static/app.js?v=" in page



def test_my_mails_explains_mails_in_progress(client):
    sign_up_and_in(client)
    page = client.get("/mails").text
    assert "in progress" in page and "not marked as sent or abandoned" in page


def test_figures_and_tags_use_the_main_font_and_inputs_are_styled():
    css = CSS.read_text()
    for selector in (".amount {", ".size {", ".kicker {", ".pill {"):
        block = css.split(selector, 1)[1].split("}", 1)[0]
        assert "var(--font-mono)" not in block, selector
    assert 'input[type="checkbox"], input[type="radio"] {' in css
    assert "appearance: none" in css


def test_notices_are_soft_with_a_left_mark():
    css = CSS.read_text()
    block = css.split(".notice {", 1)[1].split("}", 1)[0]
    assert "border-left: 3px solid" in block and "border: 0" in block
    for kind in ("warning", "error", "success"):
        rule = css.split(f".notice-{kind} {{", 1)[1].split("}", 1)[0]
        assert "border-left-color" in rule and "background" in rule, kind
