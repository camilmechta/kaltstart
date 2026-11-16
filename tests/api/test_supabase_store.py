"""SupabaseAppStore driven offline: the client talks to an httpx.MockTransport."""

import json
from datetime import date, datetime, timezone
from urllib.parse import unquote

import httpx
from supabase import ClientOptions, create_client

from kaltstart.api.rules import Refusal
from kaltstart.api.store import ListFilters, NewMail
from kaltstart.api.supabase_store import SupabaseAppStore

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


class Recorder:
    def __init__(self, tables=None, rpc=None, update=None):
        self.tables = tables or {}
        self.rpc = rpc
        self.update = update if update is not None else []
        self.requests: list[httpx.Request] = []

    def __call__(self, request):
        self.requests.append(request)
        path = request.url.path.rsplit("/", 1)[1]
        if "/rpc/" in request.url.path:
            return httpx.Response(200, json=self.rpc)
        if request.method == "PATCH":
            return httpx.Response(200, json=self.update)
        if request.method == "GET":
            return httpx.Response(200, json=self.tables.get(path, []))
        return httpx.Response(201, json=[])

    def of(self, method, table):
        return [r for r in self.requests if r.method == method and r.url.path.endswith("/" + table)]


def store(recorder):
    http = httpx.Client(transport=httpx.MockTransport(recorder))
    return SupabaseAppStore(create_client("http://localhost:54321", "test-key",
                                          options=ClientOptions(httpx_client=http)))


def param(request, name):
    return unquote(request.url.params[name])


TABLES = {
    "rounds": [
        {"id": "r1", "company_id": "c1", "date": "2026-10-01", "stage": "Seed", "amount_eur": 2000000,
         "amount_native": None, "currency": None, "size_category": "small",
         "investors": ["Example Ventures"], "source_url": "https://example.com/r1"},
        {"id": "r0", "company_id": "c1", "date": "2026-01-01", "stage": "Pre-Seed", "amount_eur": None,
         "amount_native": None, "currency": None, "size_category": "small", "investors": [],
         "source_url": "https://example.com/r0"},
        {"id": "r2", "company_id": "c2", "date": "2026-09-01", "stage": "Series A", "amount_eur": 8000000,
         "amount_native": None, "currency": None, "size_category": "medium", "investors": [],
         "source_url": "https://example.com/r2"}],
    "companies": [
        {"id": "c1", "name": "Example One", "country": "Switzerland", "city": "Zurich",
         "sectors": ["Robotics"], "website": "https://one.example.ch", "description": "Robots."},
        {"id": "c2", "name": "Example Two", "country": "Germany", "city": "Berlin",
         "sectors": ["Fintech"], "website": "https://two.example.de", "description": "Money."}],
    "contact_emails": [{"company_id": "c1"}, {"company_id": "c2"}],
    "contact_exclusions": [{"company_id": "c2", "person_key": None, "address_key": None}],
    "mails": [],
}


def test_companies_combine_the_latest_round_and_the_listing_rules():
    recorder = Recorder(TABLES)
    rows, total = store(recorder).companies(ListFilters(), "s1", NOW)
    assert total == 1 and rows[0].id == "c1"
    assert (rows[0].round_id, rows[0].stage, rows[0].sector) == ("r1", "Seed", "Robotics")
    assert param(recorder.of("GET", "rounds")[0], "date") == "gte.2025-11-16"


def test_reserve_calls_the_sql_function():
    ok = Recorder(rpc={"ok": True, "id": "m1"})
    mail = NewMail("c1", "r1", "info@one.example.ch", "generic", None, "k", "team", None,
                   "direct", "en", None, False, "Subject", "Body")
    assert store(ok).reserve("s1", mail, NOW) == "m1"
    body = json.loads(ok.requests[0].content)
    assert (body["p_student_id"], body["p_company_id"], body["p_person_key"]) == ("s1", "c1", "k")
    assert body["p_row"]["subject"] == "Subject" and "company_id" not in body["p_row"]
    full = Recorder(rpc={"ok": False, "reason": "company_full", "frees_on": "2026-12-01"})
    assert store(full).reserve("s1", mail, NOW) == Refusal("company_full", date(2026, 12, 1))


def test_set_status_is_limited_to_the_students_own_mail():
    recorder = Recorder(update=[{"id": "m1"}])
    assert store(recorder).set_status("s1", "m1", "sent", NOW)
    request = recorder.of("PATCH", "mails")[0]
    assert param(request, "id") == "eq.m1" and param(request, "student_id") == "eq.s1"
    assert json.loads(request.content)["sent_at"] == NOW.isoformat()
    assert not store(Recorder(update=[])).set_status("s1", "m1", "sent", NOW)
    assert not store(Recorder()).set_status("s1", "m1", "deleted", NOW)


def test_delete_student_anonymises_mails_then_removes_the_rest():
    recorder = Recorder()
    store(recorder).delete_student("s1")
    update = recorder.of("PATCH", "mails")[0]
    assert param(update, "student_id") == "eq.s1"
    assert json.loads(update.content) == {"student_id": None, "subject": None, "body": None,
                                          "person_name": None, "person_source_url": None,
                                          "address": None, "company_line": None}
    assert recorder.of("DELETE", "showcases") and recorder.of("DELETE", "profiles")


def test_invitation_code_is_read_from_app_settings():
    recorder = Recorder({"app_settings": [{"value": "code-123"}]})
    assert store(recorder).invitation_code() == "code-123"
    assert param(recorder.of("GET", "app_settings")[0], "key") == "eq.invitation_code"


def test_companies_with_a_person_read_contact_people():
    tables = dict(TABLES, contact_exclusions=[], contact_people=[{"company_id": "c2"}])
    recorder = Recorder(tables)
    rows, _ = store(recorder).companies(ListFilters(with_person=True), "s1", NOW)
    assert [r.id for r in rows] == ["c2"]
