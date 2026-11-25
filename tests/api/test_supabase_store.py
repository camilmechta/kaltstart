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
    "contact_emails": [{"company_id": "c1", "address": "info@c1.example.ch", "type": "generic"},
                       {"company_id": "c2", "address": "info@c2.example.ch", "type": "generic"}],
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


def test_an_invitation_code_is_checked_by_the_database():
    yes = Recorder(rpc=True)
    assert store(yes).invitation_ok(" ks-abc ") is True
    request = yes.requests[0]
    assert request.url.path.endswith("/rpc/invitation_code_ok")
    assert json.loads(request.content) == {"p_code": "ks-abc"}
    assert store(Recorder(rpc=False)).invitation_ok("KS-ABC") is False
    empty = Recorder(rpc=True)
    assert store(empty).invitation_ok("  ") is False and empty.requests == []


def test_companies_with_a_person_read_contact_people():
    tables = dict(TABLES, contact_exclusions=[], contact_people=[{"company_id": "c2"}])
    recorder = Recorder(tables)
    rows, _ = store(recorder).companies(ListFilters(with_person=True), "s1", NOW)
    assert [r.id for r in rows] == ["c2"]


def test_reserve_sends_the_variant_the_size_and_the_limits():
    from kaltstart.api.rules import LIMITS
    ok = Recorder(rpc={"ok": True, "id": "m1"})
    mail = NewMail("c1", "r1", "info@one.example.ch", "generic", None, None, "team", None,
                   "direct", "en", None, False, "Subject", "Body", variant=4,
                   size_category="small")
    store(ok).reserve("s1", mail, NOW)
    row = json.loads(ok.requests[0].content)["p_row"]
    assert (row["variant"], row["size_category"]) == (4, "small")
    assert row["limits"] == LIMITS.as_json()
    speed = Recorder(rpc={"ok": False, "reason": "student_speed", "frees_on": "2026-11-20"})
    assert store(speed).reserve("s1", mail, NOW) == Refusal("student_speed", date(2026, 11, 20))


def test_mail_records_know_the_round_and_whether_the_text_was_copied():
    rows = [{"id": "m1", "student_id": "s1", "company_id": "c1", "person_key": None,
             "status": "abandoned", "created_at": "2026-11-10T10:00:00+00:00",
             "round_id": "r1", "copied_at": "2026-11-10T11:00:00+00:00"},
            {"id": "m2", "student_id": "s2", "company_id": "c1", "person_key": None,
             "status": "abandoned", "created_at": "2026-11-10T10:00:00+00:00",
             "round_id": "r1", "copied_at": None}]
    records = store(Recorder(tables={"mails": rows})).mail_records()
    assert [(r.round_id, r.copied) for r in records] == [("r1", True), ("r1", False)]


def test_a_company_page_follows_the_stores_clock():
    from datetime import timedelta
    tables = dict(TABLES, contact_emails=[{"company_id": "c1", "address": "info@one.example.ch",
                                           "type": "generic", "source_url": "https://one.example.ch"}])
    recorder = Recorder(tables=tables)
    http = httpx.Client(transport=httpx.MockTransport(recorder))
    client = create_client("http://localhost:54321", "test-key",
                           options=ClientOptions(httpx_client=http))
    later = NOW + timedelta(days=800)
    SupabaseAppStore(client, now=lambda: later).company("c1")
    since = (later - timedelta(days=365)).date().isoformat()
    assert param(recorder.of("GET", "rounds")[0], "date") == f"gte.{since}"


def test_the_live_store_sets_unfit_addresses_aside():
    """Honest addresses, point 3: a company with only support@ counts as without address."""
    tables = dict(TABLES, contact_emails=[{"company_id": "c1", "address": "support@c1.example.ch", "type": "generic"},
                                          {"company_id": "c2", "address": "info@c2.example.ch", "type": "generic"}])
    assert store(Recorder(tables))._with_address() == {"c2"}


def test_a_person_removed_on_request_is_found_by_key():
    tables = dict(TABLES, contact_exclusions=[
        {"id": 1, "company_id": "c1", "person_key": "k-mia", "address_key": None}])
    recorder = Recorder(tables)
    live = store(recorder)
    live.person_excluded("c1", "k-mia")
    request = recorder.of("GET", "contact_exclusions")[-1]
    assert param(request, "company_id") == "eq.c1" and param(request, "person_key") == "eq.k-mia"


def test_no_reply_is_stored_with_its_date_and_read_back():
    recorder = Recorder(update=[{"id": "m1"}])
    assert store(recorder).set_status("s1", "m1", "no_reply", NOW)
    assert json.loads(recorder.of("PATCH", "mails")[0].content)["no_reply_at"] == NOW.isoformat()
    from kaltstart.api.supabase_store import _MAIL_COLUMNS
    assert "no_reply_at" in _MAIL_COLUMNS.split(",")


def test_mail_records_carry_the_sent_date():
    recorder = Recorder(tables={"mails": [{
        "id": "m1", "student_id": "s1", "company_id": "c1", "person_key": None,
        "status": "sent", "created_at": NOW.isoformat(), "round_id": None, "copied_at": None,
        "sent_at": NOW.isoformat()}]})
    [record] = store(recorder).mail_records()
    assert record.sent_at == NOW
    assert "sent_at" in unquote(str(recorder.of("GET", "mails")[0].url))


def test_a_persons_own_address_with_a_refused_word_is_kept_from_supabase():
    rows = [{"address": "maria.rosales@c1.example.ch", "type": "personal",
             "source_url": "https://c1.example.ch/team", "company_id": "c1"},
            {"address": "sales@c1.example.ch", "type": "generic",
             "source_url": "https://c1.example.ch/contact", "company_id": "c1"}]
    recorder = Recorder(tables={"contact_emails": rows})
    assert [e.address for e in store(recorder).emails("c1")] == ["maria.rosales@c1.example.ch"]
    assert store(Recorder(tables={"contact_emails": rows}))._with_address() == {"c1"}
    only_sales = [r for r in rows if r["type"] == "generic"]
    assert store(Recorder(tables={"contact_emails": only_sales}))._with_address() == set()


def test_the_live_store_reads_an_old_general_recruiting_address_as_careers():
    """D110: addresses stored as general before the recruiting words were added."""
    tables = dict(TABLES, contact_emails=[
        {"company_id": "c1", "address": "work@c1.example.ch", "type": "generic", "source_url": None},
        {"company_id": "c1", "address": "info@c1.example.ch", "type": "generic", "source_url": None}])
    live = store(Recorder(tables))
    assert {e.address: e.type for e in live.emails("c1")} == {
        "work@c1.example.ch": "careers", "info@c1.example.ch": "generic"}
    assert live.contact_summary(["c1"])["c1"][1] is True


def test_the_live_store_reads_the_last_successful_sync():
    """D111: the end of the latest successful sync or backfill."""
    recorder = Recorder(dict(TABLES, sync_runs=[{"finished_at": "2026-11-16T03:12:30+00:00"}]))
    assert store(recorder).last_update() == datetime(2026, 11, 16, 3, 12, 30, tzinfo=timezone.utc)
    request = recorder.of("GET", "sync_runs")[0]
    assert param(request, "status") == "eq.success"
    assert param(request, "command") == "in.(backfill,sync)"
    assert param(request, "order") == "finished_at.desc"


def test_the_live_store_has_no_update_before_the_first_run():
    assert store(Recorder(dict(TABLES, sync_runs=[]))).last_update() is None
