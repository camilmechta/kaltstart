"""Accounts. Supabase Auth in production, a fake in tests and in `--dev`.

The server makes every call; the browser never talks to Supabase. The
invitation code is checked by the app first, then again by the database
trigger of migration 0004, which rejects a direct call without it."""

import hashlib
import os
import secrets
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Tokens:
    access: str
    refresh: str


# Why a sign-in failed, so the page can say what to do (design 2026-11-19).
SIGN_IN_REASONS = ("credentials", "unconfirmed", "busy", "unavailable")
# What a password reset can end with.
RESET_RESULTS = ("ok", "expired", "weak", "unavailable")


def sign_in_reason(exc: Exception) -> str:
    """The reason of a failed Supabase sign-in, from its error code."""
    code, status = getattr(exc, "code", None), getattr(exc, "status", None)
    if code == "invalid_credentials":
        return "credentials"
    if code == "email_not_confirmed":
        return "unconfirmed"
    if status == 429:
        return "busy"
    return "unavailable"


class Auth(Protocol):
    def sign_up(self, email: str, password: str, invitation_code: str) -> bool: ...
    def sign_in(self, email: str, password: str) -> Tokens | str: ...
    def request_password_reset(self, email: str) -> None: ...
    def reset_password(self, token_hash: str, password: str) -> str: ...
    def reset_password_with_session(self, access_token: str, refresh_token: str,
                                    password: str) -> str: ...
    def refresh(self, refresh_token: str) -> Tokens | None: ...
    def user_id(self, access_token: str) -> str | None: ...
    def delete_user(self, user_id: str) -> None: ...
    def sign_out(self, access_token: str) -> None: ...


class FakeAuth:
    """Accounts in memory, confirmed at once. Passwords are hashed anyway."""

    def __init__(self) -> None:
        self.users: dict[str, tuple[str, str, str]] = {}      # email -> (salt, hash, id)
        self._access: dict[str, str] = {}
        self._refresh: dict[str, str] = {}
        self.reset_tokens: dict[str, str] = {}             # token hash -> email
        self.fail_sign_in_with: str | None = None          # a reason, to test the pages
        self.refused_passwords: set[str] = set()           # refused as Supabase would

    @staticmethod
    def _hash(salt: str, password: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()

    def sign_up(self, email: str, password: str, invitation_code: str) -> bool:
        email = email.strip().lower()
        if not email or email in self.users or len(password) < 8:
            return False
        salt = secrets.token_hex(8)
        self.users[email] = (salt, self._hash(salt, password), secrets.token_hex(8))
        return True

    def _tokens(self, user_id: str) -> Tokens:
        tokens = Tokens(secrets.token_urlsafe(16), secrets.token_urlsafe(16))
        self._access[tokens.access] = user_id
        self._refresh[tokens.refresh] = user_id
        return tokens

    def sign_in(self, email: str, password: str) -> Tokens | str:
        if self.fail_sign_in_with:
            return self.fail_sign_in_with
        user = self.users.get(email.strip().lower())
        if not user or not secrets.compare_digest(user[1], self._hash(user[0], password)):
            return "credentials"
        return self._tokens(user[2])

    def request_password_reset(self, email: str) -> None:
        email = email.strip().lower()
        if email in self.users:
            self.reset_tokens[secrets.token_hex(16)] = email

    def reset_password(self, token_hash: str, password: str) -> str:
        email = self.reset_tokens.pop(token_hash, None)
        if email is None or email not in self.users:
            return "expired"
        if password in self.refused_passwords:
            return "weak"                                  # the token is spent, as in Supabase
        _salt, _hash, user_id = self.users[email]
        salt = secrets.token_hex(8)
        self.users[email] = (salt, self._hash(salt, password), user_id)
        self._access = {t: u for t, u in self._access.items() if u != user_id}
        self._refresh = {t: u for t, u in self._refresh.items() if u != user_id}
        return "ok"

    def reset_password_with_session(self, access_token: str, refresh_token: str,
                                    password: str) -> str:
        """In the fake, the recovery session is the reset token itself."""
        return self.reset_password(access_token, password)

    def refresh(self, refresh_token: str) -> Tokens | None:
        user_id = self._refresh.pop(refresh_token, None)
        return self._tokens(user_id) if user_id else None

    def user_id(self, access_token: str) -> str | None:
        return self._access.get(access_token)

    def delete_user(self, user_id: str) -> None:
        self.users = {e: u for e, u in self.users.items() if u[2] != user_id}
        self._access = {t: u for t, u in self._access.items() if u != user_id}

    def sign_out(self, access_token: str) -> None:
        """Every session of the user ends, as Supabase's global sign-out."""
        user_id = self._access.get(access_token)
        self._access = {t: u for t, u in self._access.items() if u != user_id}
        self._refresh = {t: u for t, u in self._refresh.items() if u != user_id}


class SupabaseAuth:
    """Supabase Auth through the server. A new client per call, so that no
    session is ever shared between students."""

    def __init__(self, url: str, anon_key: str, service_key: str) -> None:
        self._url, self._anon, self._service = url, anon_key, service_key

    @classmethod
    def from_env(cls) -> "SupabaseAuth":
        values = [os.environ.get(name) for name in
                  ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY")]
        if not all(values):
            raise RuntimeError("SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_KEY must be set")
        return cls(*values)

    def _client(self, key: str):
        from supabase import create_client
        return create_client(self._url, key)

    def sign_up(self, email: str, password: str, invitation_code: str) -> bool:
        try:
            self._client(self._anon).auth.sign_up({
                "email": email, "password": password,
                "options": {"data": {"invitation_code": invitation_code}}})
            return True
        except Exception:
            return False

    def sign_in(self, email: str, password: str) -> Tokens | str:
        try:
            session = self._client(self._anon).auth.sign_in_with_password(
                {"email": email, "password": password}).session
        except Exception as exc:
            return sign_in_reason(exc)
        return Tokens(session.access_token, session.refresh_token) if session else "unavailable"

    def request_password_reset(self, email: str) -> None:
        """Supabase sends its standard e-mail. Its link checks the token at
        Supabase, then opens the site with a recovery session in the URL
        fragment (implicit flow: no code verifier to keep between requests).
        Nothing tells whether the address has an account."""
        try:
            from supabase import create_client
            from supabase.lib.client_options import SyncClientOptions
            create_client(self._url, self._anon, SyncClientOptions(flow_type="implicit")) \
                .auth.reset_password_for_email(email)
        except Exception:
            pass

    def reset_password(self, token_hash: str, password: str) -> str:
        """The recovery token is spent here, never on opening the link. The new
        password is set on that session, then every session is signed out."""
        client = self._client(self._anon)
        try:
            session = client.auth.verify_otp({"token_hash": token_hash, "type": "recovery"}).session
        except Exception as exc:
            # Only a refusal of the token itself means the link is spent; a
            # limit (429), a server error or no answer at all is a pause.
            status = getattr(exc, "status", None)
            return "expired" if status in (400, 401, 403, 404, 410, 422) else "unavailable"
        if not session:
            return "expired"
        try:
            client.auth.update_user({"password": password})
        except Exception as exc:
            return "weak" if getattr(exc, "code", None) in ("weak_password", "same_password") \
                else "unavailable"
        self.sign_out(session.access_token)
        return "ok"

    def reset_password_with_session(self, access_token: str, refresh_token: str,
                                    password: str) -> str:
        """The recovery session from the link's fragment, as Supabase gave it to
        the browser: the new password is set on it, then every session ends."""
        client = self._client(self._anon)
        try:
            session = client.auth.set_session(access_token, refresh_token).session
        except Exception as exc:
            status = getattr(exc, "status", None)
            return "unavailable" if status == 429 or (status or 0) >= 500 else "expired"
        if not session:
            return "expired"
        try:
            client.auth.update_user({"password": password})
        except Exception as exc:
            return "weak" if getattr(exc, "code", None) in ("weak_password", "same_password") \
                else "unavailable"
        self.sign_out(session.access_token)
        return "ok"

    def refresh(self, refresh_token: str) -> Tokens | None:
        try:
            session = self._client(self._anon).auth.refresh_session(refresh_token).session
        except Exception:
            return None
        return Tokens(session.access_token, session.refresh_token) if session else None

    def user_id(self, access_token: str) -> str | None:
        try:
            response = self._client(self._anon).auth.get_user(access_token)
        except Exception:
            return None
        return response.user.id if response and response.user else None

    def delete_user(self, user_id: str) -> None:
        self._client(self._service).auth.admin.delete_user(user_id)

    def sign_out(self, access_token: str) -> None:
        """Revokes every refresh token of the user (Supabase global sign-out)."""
        try:
            self._client(self._anon).auth.admin.sign_out(access_token, "global")
        except Exception:
            pass                    # an expired token: its session is ending anyway
