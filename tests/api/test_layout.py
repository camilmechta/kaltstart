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


JS = CSS.with_name("app.js")


def test_motion_stops_when_the_system_asks_for_less():
    css = CSS.read_text()
    rule = css.split("@media (prefers-reduced-motion: reduce)", 1)[1].split("}\n", 2)
    assert "animation: none" in "".join(rule[:2])
    for name in ("@keyframes reveal", "@keyframes unlock", "@keyframes pop", "@keyframes draw"):
        assert name in css, name


def test_the_script_plays_the_landing_example_once_and_animates_copy():
    js = JS.read_text()
    assert "IntersectionObserver" in js and "matchMedia(\"(prefers-reduced-motion: reduce)\")" in js
    assert "copied-check" in js and "pop" in js


def test_the_landing_example_is_ready_to_play(client):
    page = client.get("/").text
    example = page.split("product-example", 1)[1]
    assert "data-play" in example and example.count('class="type-line"') >= 4


# --- owner's landing feedback, 2026-11-17 --------------------------------------

def header(page):
    return page.split('<header class="nav">', 1)[1].split("</header>", 1)[0]


def test_a_visitor_can_create_an_account_from_the_top_right(client):
    top = header(client.get("/").text)
    assert 'class="nav-actions"' in top
    assert 'href="/signin"' in top and 'class="btn btn-primary btn-small nav-account" href="/signup"' in top
    assert "<svg" in top.split("nav-account", 1)[1].split("</a>", 1)[0]    # a person icon


def test_the_theme_switch_is_an_icon_button_in_the_header(client):
    page = client.get("/").text
    top = header(page)
    assert 'class="theme-toggle"' in top and 'data-theme-toggle' in top
    assert 'aria-label="Switch between light and dark"' in top
    toggle = top.split('class="theme-toggle"', 1)[1].split("</button>", 1)[0]
    assert toggle.count("<svg") == 2                                     # sun and moon
    assert "Light / dark" not in page


def test_the_signed_in_header_keeps_the_switch(client):
    sign_up_and_in(client)
    top = header(client.get("/companies").text)
    assert 'class="theme-toggle"' in top and 'action="/signout"' in top
    assert 'href="/signup"' not in top


def test_how_it_works_is_three_cards_and_a_separate_final_call(client):
    page = client.get("/").text
    how = page.split('class="how-cards"', 1)[1].split("</ol>", 1)[0]
    assert how.count('class="how-card"') == 3
    final = page.split('final-cta"', 1)[1].split("</section>", 1)[0]
    assert 'href="/signup"' in final and "invitation code" in final


def test_the_landing_moves_a_little_more_and_stops_when_asked():
    css = CSS.read_text()
    assert "@keyframes rise" in css and ".rise {" in css
    assert "[data-reveal].revealed" in css
    js = CSS.with_name("app.js").read_text()
    assert "[data-reveal]" in js
