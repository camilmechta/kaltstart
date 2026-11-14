import httpx
import pytest

from kaltstart.contacts.fetcher import SiteFetcher, default_http_client

HTML = {"content-type": "text/html; charset=utf-8"}


def page(*hrefs, text="x" * 50):
    anchors = "".join(f'<a href="{h}">{h}</a>' for h in hrefs)
    return f"<html><body><p>{text}</p>{anchors}</body></html>"


class Site:
    """A fake web: maps URL to (status, headers, body) or an exception."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def __call__(self, request):
        url = str(request.url)
        self.requests.append(request)
        route = self.routes.get(url, (404, {}, ""))
        if isinstance(route, Exception):
            raise route
        status, headers, body = route
        if isinstance(body, bytes):
            return httpx.Response(status, headers=headers, content=body)
        return httpx.Response(status, headers=headers, text=body)

    @property
    def urls(self):
        return [str(r.url) for r in self.requests]


def fetcher(site, **kwargs):
    sleeps = []
    client = httpx.Client(transport=httpx.MockTransport(site), follow_redirects=True)
    return SiteFetcher(client, sleep=sleeps.append, **kwargs), sleeps


ROBOTS_OK = (200, {"content-type": "text/plain"}, "User-agent: *\nDisallow:\n")


def simple_site(**extra):
    routes = {
        "https://example.ch/robots.txt": ROBOTS_OK,
        "https://example.ch/": (200, HTML, page("/team", "/kontakt")),
        "https://example.ch/team": (200, HTML, page()),
        "https://example.ch/kontakt": (200, HTML, page()),
    }
    routes.update(extra)
    return Site(routes)


def test_robots_txt_is_requested_first():
    site = simple_site()
    f, _ = fetcher(site)
    f.fetch_site("https://example.ch")
    assert site.urls[0] == "https://example.ch/robots.txt"


def test_robots_forbidding_home_page_fetches_nothing_else():
    site = simple_site(**{"https://example.ch/robots.txt":
                          (200, {"content-type": "text/plain"}, "User-agent: *\nDisallow: /\n")})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "robots_forbidden"
    assert outcome.pages == ()
    assert len(site.requests) == 1


def test_robots_disallowed_page_is_skipped():
    site = simple_site(**{"https://example.ch/robots.txt":
                          (200, {"content-type": "text/plain"}, "User-agent: *\nDisallow: /team\n")})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert "https://example.ch/team" not in site.urls
    assert "https://example.ch/kontakt" in site.urls
    assert outcome.status == "ok"


@pytest.mark.parametrize("robots", [
    (404, {}, ""),
    (403, {}, "forbidden"),
    (200, HTML, "<html><body>Disallow: /</body></html>"),
])
def test_missing_or_unusable_robots_means_no_restriction(robots):
    site = simple_site(**{"https://example.ch/robots.txt": robots})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "ok"
    assert outcome.pages[0].url == "https://example.ch/"


def test_network_failure_on_robots_is_unreachable_not_forbidden():
    # Seen on a real run: the machine lost its network and every site was
    # reported as forbidding robots. No page is fetched either way, but the
    # cause must say whose fault it is.
    site = simple_site(**{"https://example.ch/robots.txt": httpx.ConnectError("boom")})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "unreachable"
    assert site.urls == ["https://example.ch/robots.txt"]


@pytest.mark.parametrize("robots", [
    (500, {}, "error"),
    (503, {}, "busy"),
])
def test_robots_that_cannot_be_read_forbids_the_site(robots):
    # RFC 9309: when robots.txt is unreachable, assume everything is disallowed.
    site = simple_site(**{"https://example.ch/robots.txt": robots})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "robots_forbidden"
    assert site.urls == ["https://example.ch/robots.txt"]


def test_rules_addressed_to_our_own_user_agent_are_obeyed():
    rules = "User-agent: python-httpx\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    site = simple_site(**{"https://example.ch/robots.txt":
                          (200, {"content-type": "text/plain"}, rules)})
    f, _ = fetcher(site)
    assert f.fetch_site("https://example.ch").status == "robots_forbidden"


def test_fetches_home_then_chosen_links_with_kinds():
    f, _ = fetcher(simple_site())
    outcome = f.fetch_site("https://example.ch")
    assert [(p.url, p.kind) for p in outcome.pages] == [
        ("https://example.ch/", "home"),
        ("https://example.ch/kontakt", "contact"),
        ("https://example.ch/team", "team"),
    ]
    assert outcome.hosts == ("example.ch",)
    assert "<html>" in outcome.pages[0].html


def test_waits_two_seconds_between_requests(monkeypatch):
    monkeypatch.setattr("kaltstart.contacts.fetcher.time.monotonic", lambda: 100.0)
    site = simple_site()
    f, sleeps = fetcher(site)
    f.fetch_site("https://example.ch")
    # 4 requests (robots, home, 2 pages): a wait before each one but the first.
    assert sleeps == [2.0, 2.0, 2.0]


def test_never_more_than_eight_pages():
    hrefs = [f"/{w}/{i}" for w in ("impressum", "kontakt", "team", "jobs") for i in range(3)]
    routes = {"https://example.ch/robots.txt": ROBOTS_OK,
              "https://example.ch/": (200, HTML, page(*hrefs))}
    routes.update({f"https://example.ch{h}": (200, HTML, page()) for h in hrefs})
    f, _ = fetcher(Site(routes))
    assert len(f.fetch_site("https://example.ch").pages) == 8


def test_home_redirect_to_another_domain_is_accepted():
    site = Site({
        "https://example.ch/robots.txt": ROBOTS_OK,
        "https://example.ch/": (301, {"location": "https://www.example.com/"}, ""),
        "https://www.example.com/": (200, HTML, page("https://example.com/team")),
        "https://example.com/team": (200, HTML, page()),
    })
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.hosts == ("example.ch", "example.com")
    assert [p.url for p in outcome.pages] == [
        "https://www.example.com/", "https://example.com/team"]


def test_page_redirecting_off_site_is_dropped():
    site = simple_site(**{
        "https://example.ch/kontakt": (302, {"location": "https://other.example.de/"}, ""),
        "https://other.example.de/": (200, HTML, page()),
    })
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert [p.url for p in outcome.pages] == ["https://example.ch/", "https://example.ch/team"]
    assert not any("other.example.de" in url for url in site.urls)


def test_redirects_to_other_hosts_are_never_requested():
    site = simple_site(**{
        "https://example.ch/": (200, HTML, page("/team", "/jobs")),
        "https://example.ch/team": (301, {"location": "https://www.linkedin.com/company/example"}, ""),
        "https://example.ch/jobs": (302, {"location": "https://jobs.example-ats.com/example"}, ""),
        "https://www.linkedin.com/company/example": (200, HTML, page()),
        "https://jobs.example-ats.com/example": (200, HTML, page()),
    })
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert [p.url for p in outcome.pages] == ["https://example.ch/"]
    assert all(httpx.URL(url).host == "example.ch" for url in site.urls)


def test_home_redirect_to_a_social_network_is_unreachable():
    site = simple_site(**{
        "https://example.ch/": (301, {"location": "https://www.linkedin.com/company/example"}, ""),
        "https://www.linkedin.com/company/example": (200, HTML, page("/company/example/people")),
        "https://www.linkedin.com/robots.txt": ROBOTS_OK,
    })
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "unreachable"
    assert outcome.hosts == ("example.ch",)
    assert not any("linkedin" in url for url in site.urls)


@pytest.mark.parametrize("website", [
    "https://www.linkedin.com/company/example",
    "https://facebook.com/example",
    "https://linktr.ee/example",
])
def test_website_that_is_a_social_profile_is_refused(website):
    site = Site({})
    f, _ = fetcher(site)
    assert f.fetch_site(website).status == "unreachable"
    assert site.requests == []


def test_new_host_robots_is_read_before_the_redirect_target():
    site = Site({
        "https://example.ch/robots.txt": ROBOTS_OK,
        "https://example.ch/": (301, {"location": "https://www.example.com/"}, ""),
        "https://www.example.com/robots.txt":
            (200, {"content-type": "text/plain"}, "User-agent: *\nDisallow: /\n"),
        "https://www.example.com/": (200, HTML, page()),
    })
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "robots_forbidden"
    assert site.urls == ["https://example.ch/robots.txt", "https://example.ch/",
                         "https://www.example.com/robots.txt"]


def test_each_origin_has_its_own_robots():
    site = simple_site(**{
        "https://example.ch/": (200, HTML, page("https://jobs.example.ch/karriere", "/kontakt")),
        "https://jobs.example.ch/robots.txt":
            (200, {"content-type": "text/plain"}, "User-agent: *\nDisallow: /\n"),
        "https://jobs.example.ch/karriere": (200, HTML, page()),
    })
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert "https://jobs.example.ch/karriere" not in site.urls
    assert [p.url for p in outcome.pages] == ["https://example.ch/", "https://example.ch/kontakt"]


def test_redirect_hops_are_throttled_too(monkeypatch):
    monkeypatch.setattr("kaltstart.contacts.fetcher.time.monotonic", lambda: 100.0)
    site = Site({
        "https://example.ch/robots.txt": ROBOTS_OK,
        "https://example.ch/": (301, {"location": "https://www.example.ch/"}, ""),
        "https://www.example.ch/robots.txt": ROBOTS_OK,
        "https://www.example.ch/": (200, HTML, page()),
    })
    f, sleeps = fetcher(site)
    assert f.fetch_site("https://example.ch").status == "ok"
    assert site.urls[:4] == [
        "https://example.ch/robots.txt", "https://example.ch/",
        "https://www.example.ch/robots.txt", "https://www.example.ch/"]
    # One wait before every request but the first, redirect hops included.
    assert sleeps == [2.0] * (len(site.requests) - 1)


def test_too_many_redirects_is_unreachable():
    routes = {"https://example.ch/robots.txt": ROBOTS_OK}
    for i in range(10):
        routes[f"https://example.ch/{i if i else ''}"] = (
            302, {"location": f"https://example.ch/{i + 1}"}, "")
    f, _ = fetcher(Site(routes))
    assert f.fetch_site("https://example.ch").status == "unreachable"


def test_non_html_and_oversized_pages_are_skipped():
    site = simple_site(**{
        "https://example.ch/team": (200, {"content-type": "application/pdf"}, b"%PDF-1.4"),
        "https://example.ch/kontakt": (200, HTML, "<html>" + "x" * 3_000_000 + "</html>"),
    })
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "ok"
    assert [p.url for p in outcome.pages] == ["https://example.ch/"]


def test_undecodable_bytes_do_not_crash():
    site = simple_site(**{"https://example.ch/": (200, HTML, b"<html><body>caf\xff\xfe</body></html>")})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "ok"
    assert "caf" in outcome.pages[0].html


@pytest.mark.parametrize("home", [
    (500, {}, "error"),
    httpx.ConnectError("boom"),
    httpx.ReadTimeout("slow"),
])
def test_unreachable_when_home_page_fails(home):
    site = simple_site(**{"https://example.ch/": home})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "unreachable"
    assert outcome.pages == ()


def test_failing_secondary_page_is_skipped():
    site = simple_site(**{"https://example.ch/team": (404, {}, "")})
    f, _ = fetcher(site)
    outcome = f.fetch_site("https://example.ch")
    assert outcome.status == "ok"
    assert [p.url for p in outcome.pages] == ["https://example.ch/", "https://example.ch/kontakt"]


def test_website_with_a_path_is_used_as_the_home_page():
    site = Site({
        "https://example.ch/robots.txt": ROBOTS_OK,
        "https://example.ch/en/": (200, HTML, page()),
    })
    f, _ = fetcher(site)
    assert f.fetch_site("https://example.ch/en/").pages[0].url == "https://example.ch/en/"


def test_default_user_agent():
    site = simple_site()
    f, _ = fetcher(site)
    f.fetch_site("https://example.ch")
    assert all(r.headers["user-agent"].startswith("python-httpx/") for r in site.requests)


def test_default_http_client_settings():
    client = default_http_client()
    assert client.timeout == httpx.Timeout(15)
    assert client.follow_redirects is True
    assert client.headers["user-agent"].startswith("python-httpx/")
