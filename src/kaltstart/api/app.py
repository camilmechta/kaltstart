"""The FastAPI application: routes, page rendering, session handling.

Every rule is checked here or in the store, never only in the browser."""

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData

from kaltstart.api import rules
from kaltstart.api.auth import Auth, Tokens
from kaltstart.api.session import RateLimit, Sessions, client_key, csrf_ok, new_csrf, safe_next
from kaltstart.api.store import AppStore, ListFilters

HERE = Path(__file__).parent
log = logging.getLogger("kaltstart.api")


class Page:
    """Renders a template with what every page needs, and saves the session."""

    def __init__(self, env: Environment, sessions: Sessions, removal_contact: str) -> None:
        self._env, self._sessions, self._removal = env, sessions, removal_contact
        # A fingerprint of each asset in its address: a new design reaches
        # every browser at once instead of waiting for its cache to expire.
        self._versions = {name: hashlib.sha256((HERE / "static" / name).read_bytes()).hexdigest()[:10]
                          for name in ("app.css", "app.js")}

    def __call__(self, request: Request, name: str, *, status: int = 200, **context) -> HTMLResponse:
        state = request.state
        html = self._env.get_template(name).render(
            request=request, user_id=getattr(state, "user_id", None),
            csrf=state.session["csrf"], pending=getattr(state, "pending", 0),
            week=getattr(state, "week", 0), limits=rules.LIMITS,
            removal_contact=self._removal, path=request.url.path, versions=self._versions,
            **context)
        # The session cookie is saved by the middleware, on every response.
        return HTMLResponse(html, status_code=status)


def create_app(store: AppStore, auth: Auth, *, session_secret: str, removal_contact: str,
               now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
               proxy_hops: int = 0) -> FastAPI:
    """proxy_hops: how many proxies of the host stand in front of the app; the
    client's address is the entry the last of them added to X-Forwarded-For,
    never one the client wrote itself (0: the direct peer)."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    env = Environment(loader=FileSystemLoader(HERE / "templates"),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["web_link"] = web_link
    from kaltstart.contacts.names import title_hint
    env.filters["title_hint"] = title_hint
    sessions = Sessions(session_secret)
    page = Page(env, sessions, removal_contact)
    # Sign-up: 10 tries an hour per address, and sign-up closes for an hour
    # after 30 wrong invitation codes from anywhere. Sign-in: 10 tries in 15
    # minutes per address and per e-mail, so nobody can make Supabase block
    # the server's own address for every student.
    signup_limit, wrong_codes = RateLimit(10, 3600), RateLimit(30, 3600)
    # Sign-in: per computer, and per e-mail from one computer. Never per e-mail
    # alone, which let anyone who knows the address lock its owner out (D91).
    signin_by_ip, signin_by_account = RateLimit(10, 900), RateLimit(10, 900)
    # Password reset requests: the same limits as sign-in, kept apart.
    reset_by_ip, reset_by_account = RateLimit(10, 900), RateLimit(10, 900)
    app.state.store, app.state.auth, app.state.page, app.state.now = store, auth, page, now
    app.state.sessions = sessions

    def attach(request: Request) -> None:
        """Runs in a worker thread: Supabase calls never block the event loop."""
        session = sessions.load(request)
        request.state.session = session
        request.state.user_id = None
        if session.get("access"):
            user_id = auth.user_id(session["access"])
            if user_id is None and session.get("refresh"):
                tokens = auth.refresh(session["refresh"])
                if tokens:
                    session.update(access=tokens.access, refresh=tokens.refresh)
                    user_id = auth.user_id(tokens.access)
            if user_id is None:
                session.pop("access", None)
                session.pop("refresh", None)
            request.state.user_id = user_id
        if request.state.user_id:
            own = [m.record() for m in store.mails(request.state.user_id)]
            request.state.pending = rules.pending_count(request.state.user_id, own, now())
            request.state.week = rules.week_count(request.state.user_id, own, now())

    @app.middleware("http")
    async def attach_session(request: Request, call_next):
        static = request.url.path.startswith("/static/")
        try:
            if static:
                response = await call_next(request)
            else:
                await run_in_threadpool(attach, request)
                response = await call_next(request)
                # Every response keeps the session, so a refreshed token is never lost.
                sessions.save(response, request.state.session)
        except Exception as exc:
            # The route and the kind of error only: a message may quote a name,
            # an address or a mail, and logs must never hold them.
            log.error("error on %s %s: %s", request.method, request.url.path,
                      type(exc).__name__)
            response = HTMLResponse("<!doctype html><title>Kaltstart</title><p>Something went "
                                    "wrong. Please try again in a moment.</p>", status_code=500)
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        # A page, never a bare body: a browser would save a body without a
        # type as a file (the owner got a "status" download, 2026-11-17).
        return error_page(exc.status_code)

    async def posted_form(request: Request) -> FormData:
        """The posted form, after checking its CSRF token (403 otherwise). A
        dependency, so that the routes themselves are plain functions run in
        worker threads."""
        form = await request.form()
        if not csrf_ok(request.state.session, form.get("csrf")):
            raise HTTPException(403, "Forbidden")
        return form

    async def signin_form_posted(request: Request) -> FormData | None:
        """The sign-in form, or None when its token is stale but the visitor is
        already signed in: a second click on "Sign in" after the first one
        signed in and changed the token. Nothing is changed for them then."""
        form = await request.form()
        if csrf_ok(request.state.session, form.get("csrf")):
            return form
        if getattr(request.state, "user_id", None):
            return None
        raise HTTPException(403, "Forbidden")

    def signed_in(request: Request) -> RedirectResponse | None:
        if request.state.user_id:
            return None
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return redirect(request, f"/signin?next={quote(target, safe='/')}")

    def redirect(request: Request, location: str) -> RedirectResponse:
        return RedirectResponse(location, status_code=303)

    app.state.signed_in, app.state.redirect, app.state.posted_form = signed_in, redirect, posted_form

    @app.get("/")
    def home(request: Request):
        if request.state.user_id:
            return redirect(request, "/companies")
        _rows, total = store.companies(ListFilters(), "", now())
        return page(request, "landing.html", total=total)

    @app.get("/signin")
    def signin_form(request: Request):
        return page(request, "signin.html", next=request.query_params.get("next", ""),
                    reset_done=request.query_params.get("reset") == "1")

    @app.post("/signin")
    def signin(request: Request, form: FormData | None = Depends(signin_form_posted)):
        if form is None:
            return redirect(request, safe_next(request.query_params.get("next")))

        email = (form.get("email") or "").strip().lower()[:254]
        target = safe_next(request.query_params.get("next") or form.get("next"))
        computer = client_key(request, proxy_hops)
        if not (signin_by_ip.allow(computer)
                and signin_by_account.allow(f"{email} {computer}")):
            return page(request, "signin.html", status=429, next=target, email=email,
                        error="Too many attempts. Try again in 15 minutes.")
        tokens = auth.sign_in(email, form.get("password", ""))
        if not isinstance(tokens, Tokens):
            status, error = SIGN_IN_ERRORS.get(tokens, SIGN_IN_ERRORS["unavailable"])
            return page(request, "signin.html", status=status, next=target,
                        email=form.get("email", "")[:254], error=error)
        request.state.session.update(access=tokens.access, refresh=tokens.refresh,
                                     csrf=new_csrf())
        return redirect(request, target)

    @app.get("/forgot-password")
    def forgot_form(request: Request):
        return page(request, "forgot.html")

    @app.post("/forgot-password")
    def forgot(request: Request, form: FormData = Depends(posted_form)):
        email = (form.get("email") or "").strip().lower()[:254]
        computer = client_key(request, proxy_hops)
        if not (reset_by_ip.allow(computer) and reset_by_account.allow(f"{email} {computer}")):
            return page(request, "forgot.html", status=429, email=email,
                        error="Too many requests. Try again in 15 minutes.")
        if email:
            auth.request_password_reset(email)
        return page(request, "forgot.html", sent=True)

    @app.get("/reset-password")
    def reset_form(request: Request):
        return page(request, "reset.html", token_hash=request.query_params.get("token_hash", ""))

    @app.post("/reset-password")
    def reset_password(request: Request, form: FormData = Depends(posted_form)):
        token = (form.get("token_hash") or "")[:200]
        password, again = form.get("password", ""), form.get("password_again", "")
        error = None
        if len(password) < 8:
            error = "The password needs at least 8 characters."
        elif password != again:
            error = "The two passwords are not the same."
        if error is None:
            result = auth.reset_password(token, password)
            if result == "ok":
                return redirect(request, "/signin?reset=1")
            error = RESET_ERRORS.get(result, RESET_ERRORS["unavailable"])
        return page(request, "reset.html", status=400, token_hash=token, error=error)

    @app.get("/about")
    def about(request: Request):
        return page(request, "about.html")

    @app.get("/privacy")
    def privacy(request: Request):
        return page(request, "privacy.html")

    @app.get("/signup")
    def signup_form(request: Request):
        return page(request, "signup.html")

    @app.post("/signup")
    def signup(request: Request, form: FormData = Depends(posted_form)):

        if wrong_codes.full("all") or not signup_limit.allow(client_key(request, proxy_hops)):
            return page(request, "signup.html", status=429,
                        error="Too many attempts. Try again in an hour.")
        code = form.get("code", "")
        ok = store.invitation_ok(code)
        if not ok:
            wrong_codes.allow("all")
        if ok:
            ok = auth.sign_up(form.get("email", ""), form.get("password", ""), code)
        if not ok:
            return page(request, "signup.html", status=400, email=form.get("email", "")[:254],
                        error="Sign-up failed. Check your invitation code, your e-mail, and that "
                              "the password has at least 8 characters.")
        return page(request, "signup.html", done=True)

    @app.post("/signout")
    def signout(request: Request, form: FormData = Depends(posted_form)):
        session = request.state.session
        if session.get("access"):
            auth.sign_out(session["access"])      # revoked at Supabase, not only forgotten
        session.pop("access", None)
        session.pop("refresh", None)
        session["csrf"] = new_csrf()
        return redirect(request, "/signin")

    from kaltstart.api import pages
    pages.register(app)
    return app


# What the sign-in page says for each reason of auth.sign_in (design 2026-11-19).
SIGN_IN_ERRORS = {
    "credentials": (400, "Wrong e-mail or password."),
    "unconfirmed": (400, "Confirm your e-mail address first: open the link we sent you."),
    "busy": (429, "Too many sign-ins right now. Try again in a few minutes."),
    "unavailable": (503, "Sign-in is not working right now. Try again in a moment."),
}
RESET_ERRORS = {
    "expired": "This link has expired.",
    "weak": "Choose another password: this one is too weak or the same as before.",
    "unavailable": "The password could not be changed right now. Try again in a moment.",
}


# Sent with every response. Styles may be inline (style attributes in the
# templates); scripts come only from this site.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' "
                               "'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
                               "object-src 'none'; base-uri 'none'; form-action 'self'; "
                               "frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def error_page(status: int) -> HTMLResponse:
    """A short page for a refusal or a missing page, with a way back."""
    text = {403: "This form has expired. Go back, reload the page and try again.",
            404: "This page does not exist, or it is not yours."}.get(
                status, "Something went wrong. Please try again in a moment.")
    return HTMLResponse(f'<!doctype html><meta charset="utf-8"><title>Kaltstart</title>'
                        f'<p>{text}</p><p><a href="/companies">Back to the companies</a></p>',
                        status_code=status)


def web_link(url: str | None) -> str | None:
    """A link from data only if it is a web address: never javascript: or data:."""
    if url and url.strip().lower().startswith(("https://", "http://")):
        return url.strip()
    return None


def app_from_env() -> FastAPI:
    """The production app, configured from the environment (uvicorn factory)."""
    from kaltstart.api.auth import SupabaseAuth
    from kaltstart.api.supabase_store import SupabaseAppStore
    secret = os.environ.get("SESSION_SECRET")
    removal = os.environ.get("REMOVAL_CONTACT")
    if not secret or not removal:
        raise RuntimeError("SESSION_SECRET and REMOVAL_CONTACT must be set")
    return create_app(SupabaseAppStore.from_env(), SupabaseAuth.from_env(),
                      session_secret=secret, removal_contact=removal,
                      proxy_hops=int(os.environ.get("PROXY_HOPS", "1")))
