"""The session cookie, the CSRF token and the sign-up rate limit.

The cookie holds the Supabase tokens and a CSRF token, signed with
SESSION_SECRET. It is HttpOnly, Secure and SameSite=Lax; every form carries
the CSRF token and every POST checks it."""

import hmac
import secrets
import time
from collections import defaultdict, deque

from itsdangerous import BadSignature, URLSafeSerializer
from starlette.requests import Request
from starlette.responses import Response

COOKIE = "kaltstart"
COOKIE_DAYS = 14
SIGNUP_ATTEMPTS = 10
SIGNUP_WINDOW_S = 3600


class Sessions:
    def __init__(self, secret: str) -> None:
        self._serializer = URLSafeSerializer(secret, salt="session")

    def load(self, request: Request) -> dict:
        raw = request.cookies.get(COOKIE)
        try:
            data = self._serializer.loads(raw) if raw else {}
        except BadSignature:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("csrf", secrets.token_urlsafe(24))
        return data

    def save(self, response: Response, data: dict) -> None:
        response.set_cookie(COOKIE, self._serializer.dumps(data), max_age=COOKIE_DAYS * 86400,
                            httponly=True, secure=True, samesite="lax", path="/")


def csrf_ok(session: dict, submitted: str | None) -> bool:
    return bool(submitted) and hmac.compare_digest(session.get("csrf", ""), submitted)


class RateLimit:
    """At most `limit` attempts per key in a sliding window, in memory."""

    def __init__(self, limit: int = SIGNUP_ATTEMPTS, window_s: int = SIGNUP_WINDOW_S,
                 clock=time.monotonic) -> None:
        self._limit, self._window, self._clock = limit, window_s, clock
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True


def safe_next(target: str | None) -> str:
    """A path on this site, never another site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return "/companies"
