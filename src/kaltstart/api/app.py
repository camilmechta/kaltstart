"""The FastAPI application: routes, page rendering, session handling.

Every rule is checked here or in the store, never only in the browser."""

import hmac
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from kaltstart.api import rules
from kaltstart.api.auth import Auth
from kaltstart.api.session import RateLimit, Sessions, csrf_ok, safe_next
from kaltstart.api.store import AppStore

HERE = Path(__file__).parent
log = logging.getLogger("kaltstart.api")


class Page:
    """Renders a template with what every page needs, and saves the session."""

    def __init__(self, env: Environment, sessions: Sessions, removal_contact: str) -> None:
        self._env, self._sessions, self._removal = env, sessions, removal_contact

    def __call__(self, request: Request, name: str, *, status: int = 200, **context) -> HTMLResponse:
        state = request.state
        html = self._env.get_template(name).render(
            request=request, user_id=getattr(state, "user_id", None),
            csrf=state.session["csrf"], pending=getattr(state, "pending", 0),
            removal_contact=self._removal, path=request.url.path, **context)
        response = HTMLResponse(html, status_code=status)
        self._sessions.save(response, state.session)
        return response


def create_app(store: AppStore, auth: Auth, *, session_secret: str, removal_contact: str,
               now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    env = Environment(loader=FileSystemLoader(HERE / "templates"),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    sessions = Sessions(session_secret)
    page = Page(env, sessions, removal_contact)
    signup_limit = RateLimit()
    app.state.store, app.state.auth, app.state.page, app.state.now = store, auth, page, now
    app.state.sessions = sessions

    @app.middleware("http")
    async def attach_session(request: Request, call_next):
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
            request.state.pending = rules.pending_count(request.state.user_id,
                                                        store.mail_records(), now())
        try:
            return await call_next(request)
        except Exception as exc:
            # The route and the kind of error only: a message may quote a name,
            # an address or a mail, and logs must never hold them.
            log.error("error on %s %s: %s", request.method, request.url.path,
                      type(exc).__name__)
            return HTMLResponse("<!doctype html><title>Kaltstart</title><p>Something went wrong. "
                                "Please try again in a moment.</p>", status_code=500)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return Response(exc.detail or "", status_code=exc.status_code)

    async def form_of(request: Request):
        """The posted form, after checking its CSRF token (403 otherwise)."""
        form = await request.form()
        if not csrf_ok(request.state.session, form.get("csrf")):
            raise HTTPException(403, "Forbidden")
        return form

    def signed_in(request: Request) -> RedirectResponse | None:
        if request.state.user_id:
            return None
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return redirect(request, f"/signin?next={quote(target, safe='/')}")

    def redirect(request: Request, location: str) -> RedirectResponse:
        response = RedirectResponse(location, status_code=303)
        sessions.save(response, request.state.session)
        return response

    app.state.signed_in, app.state.redirect, app.state.form_of = signed_in, redirect, form_of

    @app.get("/")
    async def home(request: Request):
        return redirect(request, "/companies" if request.state.user_id else "/signin")

    @app.get("/signin")
    async def signin_form(request: Request):
        return page(request, "signin.html", next=request.query_params.get("next", ""))

    @app.post("/signin")
    async def signin(request: Request):
        form = await form_of(request)
        tokens = auth.sign_in(form.get("email", ""), form.get("password", ""))
        target = safe_next(request.query_params.get("next") or form.get("next"))
        if not tokens:
            return page(request, "signin.html", status=400, next=target,
                        error="Wrong e-mail or password, or the e-mail is not confirmed yet.")
        request.state.session.update(access=tokens.access, refresh=tokens.refresh)
        return redirect(request, target)

    @app.get("/signup")
    async def signup_form(request: Request):
        return page(request, "signup.html")

    @app.post("/signup")
    async def signup(request: Request):
        form = await form_of(request)
        ip = request.client.host if request.client else "unknown"
        if not signup_limit.allow(ip):
            return page(request, "signup.html", status=429,
                        error="Too many attempts. Try again in an hour.")
        code = form.get("code", "")
        expected = store.invitation_code()
        ok = bool(expected) and hmac.compare_digest(code.encode(), expected.encode())
        if ok:
            ok = auth.sign_up(form.get("email", ""), form.get("password", ""), code)
        if not ok:
            return page(request, "signup.html", status=400,
                        error="Sign-up failed. Check your invitation code, your e-mail, and that "
                              "the password has at least 8 characters.")
        return page(request, "signup.html", done=True)

    @app.post("/signout")
    async def signout(request: Request):
        await form_of(request)
        request.state.session.pop("access", None)
        request.state.session.pop("refresh", None)
        return redirect(request, "/signin")

    from kaltstart.api import pages
    pages.register(app)
    return app


def app_from_env() -> FastAPI:
    """The production app, configured from the environment (uvicorn factory)."""
    from kaltstart.api.auth import SupabaseAuth
    from kaltstart.api.supabase_store import SupabaseAppStore
    secret = os.environ.get("SESSION_SECRET")
    removal = os.environ.get("REMOVAL_CONTACT")
    if not secret or not removal:
        raise RuntimeError("SESSION_SECRET and REMOVAL_CONTACT must be set")
    return create_app(SupabaseAppStore.from_env(), SupabaseAuth.from_env(),
                      session_secret=secret, removal_contact=removal)
