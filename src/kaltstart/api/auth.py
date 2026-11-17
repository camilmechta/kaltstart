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


class Auth(Protocol):
    def sign_up(self, email: str, password: str, invitation_code: str) -> bool: ...
    def sign_in(self, email: str, password: str) -> Tokens | None: ...
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

    def sign_in(self, email: str, password: str) -> Tokens | None:
        user = self.users.get(email.strip().lower())
        if not user or not secrets.compare_digest(user[1], self._hash(user[0], password)):
            return None
        return self._tokens(user[2])

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

    def sign_in(self, email: str, password: str) -> Tokens | None:
        try:
            session = self._client(self._anon).auth.sign_in_with_password(
                {"email": email, "password": password}).session
        except Exception:
            return None
        return Tokens(session.access_token, session.refresh_token) if session else None

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
