"""Host and domain rules, and the text and links of an HTML page."""

from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup


def _bare(host: str) -> str:
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _is_or_under(host: str, parent: str) -> bool:
    return host == parent or host.endswith("." + parent)


def site_host(website: str) -> str:
    """Lower-case host of a website value, without a leading `www.`."""
    value = website.strip()
    if "://" not in value:
        value = "https://" + value
    return _bare(urlsplit(value).hostname or "")


# Never fetched, whatever links or redirects point to them.
SOCIAL_HOSTS = ("linkedin.com", "facebook.com", "instagram.com", "x.com",
                "twitter.com", "xing.com", "youtube.com", "tiktok.com",
                "linktr.ee")


def is_social(url: str) -> bool:
    """True for a social network or link-in-bio host: never a company's own site."""
    host = _bare(urlsplit(url).hostname or "")
    return any(_is_or_under(host, social) for social in SOCIAL_HOSTS)


def same_site(url: str, hosts: Iterable[str]) -> bool:
    """True when `url` is on one of `hosts` or on a subdomain of one."""
    host = _bare(urlsplit(url).hostname or "")
    return bool(host) and any(_is_or_under(host, h) for h in hosts)


# Subdomains that only name a part of a company's own site. The parent of
# any other subdomain may belong to someone else (a university, a site
# builder, a public suffix), so it is not trusted.
GENERIC_SUBDOMAINS = ("app", "shop", "web", "home", "get", "go", "try", "en", "de",
                      "fr", "it", "blog", "jobs", "careers", "about", "my", "portal")


def on_company_domain(email_domain: str, hosts: Iterable[str]) -> bool:
    """True for a host, a subdomain of a host, or the parent of a generic subdomain."""
    domain = email_domain.lower()
    for host in hosts:
        if _is_or_under(domain, host):
            return True
        label, _, parent = host.partition(".")
        if label in GENERIC_SUBDOMAINS and parent == domain and "." in domain:
            return True
    return False


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def visible_text(html: str) -> str:
    """Text a visitor reads: no script, style or noscript content."""
    soup = _soup(html)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


def links(html: str, base_url: str) -> list[tuple[str, str]]:
    """`(absolute_url, link_text)` for every `<a href>`, in document order."""
    found = []
    for anchor in _soup(html).find_all("a", href=True):
        url, _fragment = urldefrag(urljoin(base_url, anchor["href"].strip()))
        found.append((url, " ".join(anchor.get_text(" ").split())))
    return found
