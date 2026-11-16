"""SupabaseContactStore driven offline: the client talks to an httpx.MockTransport."""

import json
from datetime import date
from urllib.parse import unquote

import httpx
import pytest
from supabase import ClientOptions, create_client

from kaltstart.contacts.store import CANDIDATE_COLUMNS
from kaltstart.contacts.supabase_store import SupabaseContactStore

FAKE_URL = "http://localhost:54321"
FAKE_KEY = "test-key"


class Recorder:
    def __init__(self, responder=None):
        self.requests: list[httpx.Request] = []
        self.responder = responder or (lambda request: httpx.Response(200, json=[]))

    def __call__(self, request):
        self.requests.append(request)
        return self.responder(request)

    def of(self, method, table):
        return [r for r in self.requests
                if r.method == method and r.url.path == f"/rest/v1/{table}"]


def make_store(recorder):
    http = httpx.Client(transport=httpx.MockTransport(recorder))
    client = create_client(FAKE_URL, FAKE_KEY, options=ClientOptions(httpx_client=http))
    return SupabaseContactStore(client)


def body(request):
    return json.loads(request.content)


def param(request, name):
    return unquote(request.url.params[name])


def test_candidates_select_filter_and_page_past_1000_rows():
    def responder(request):
        start = int(request.headers["range"].split("-")[0]) if "range" in request.headers \
            else int(request.url.params.get("offset", 0))
        count = 1000 if start == 0 else 3
        return httpx.Response(200, json=[{"id": f"c{start + n}"} for n in range(count)])
    recorder = Recorder(responder)
    rows = make_store(recorder).candidate_companies("Switzerland")
    assert len(rows) == 1003
    requests = recorder.of("GET", "companies")
    assert len(requests) == 2
    assert param(requests[0], "select").split(",") == list(CANDIDATE_COLUMNS)
    assert param(requests[0], "country") == "eq.Switzerland"
    assert param(requests[0], "website") == "not.is.null"


def test_replace_contacts_deletes_then_inserts():
    recorder = Recorder()
    email = {"company_id": "c1", "address": "info@example.ch", "type": "generic",
             "source_url": "https://example.ch/", "read_at": "2026-11-15T03:17:00+00:00"}
    person = {"company_id": "c1", "name": "Anna Muster", "title": "Founder",
              "categories": ["leadership"], "level": "head",
              "source_url": "https://example.ch/team", "read_at": "2026-11-15T03:17:00+00:00"}
    make_store(recorder).replace_contacts("c1", [email], [person])
    methods = [(r.method, r.url.path.rsplit("/", 1)[1]) for r in recorder.requests]
    assert methods == [("DELETE", "contact_emails"), ("DELETE", "contact_people"),
                       ("POST", "contact_emails"), ("POST", "contact_people")]
    assert param(recorder.requests[0], "company_id") == "in.(c1)"
    assert body(recorder.requests[2]) == [email]
    assert body(recorder.requests[3]) == [person]


def test_replace_contacts_with_nothing_found_only_deletes():
    recorder = Recorder()
    make_store(recorder).replace_contacts("c1", [], [])
    assert [r.method for r in recorder.requests] == ["DELETE", "DELETE"]


def test_delete_contacts_batches_ids_by_100():
    recorder = Recorder()
    make_store(recorder).delete_contacts([f"c{n}" for n in range(150)])
    deletes = recorder.of("DELETE", "contact_emails")
    assert [len(param(r, "company_id")[4:-1].split(",")) for r in deletes] == [100, 50]
    assert len(recorder.of("DELETE", "contact_people")) == 2


def test_delete_contacts_of_nobody_sends_nothing():
    recorder = Recorder()
    make_store(recorder).delete_contacts([])
    assert recorder.requests == []


def test_set_contact_state_updates_one_company():
    recorder = Recorder()
    make_store(recorder).set_contact_state(
        "c1", checked_at="2026-11-15T03:17:00+00:00", outcome="ok", attempts=0,
        next_at="2026-12-15T03:17:00+00:00")
    (request,) = recorder.of("PATCH", "companies")
    assert param(request, "id") == "eq.c1"
    assert body(request) == {
        "contacts_checked_at": "2026-11-15T03:17:00+00:00", "contacts_outcome": "ok",
        "contacts_attempts": 0, "contacts_next_at": "2026-12-15T03:17:00+00:00"}


def test_rounds_since_filters_on_the_date():
    recorder = Recorder(lambda request: httpx.Response(
        200, json=[{"company_id": "c1"}, {"company_id": "c1"}, {"company_id": "c2"}]))
    ids = make_store(recorder).company_ids_with_round_since(date(2025, 11, 15))
    assert ids == {"c1", "c2"}
    request = recorder.of("GET", "rounds")[0]
    assert param(request, "date") == "gte.2025-11-15"
    assert param(request, "order") == "id.asc"          # a unique key, so that paging skips nothing


def test_contact_tables_are_paged_on_their_primary_key():
    recorder = Recorder()
    make_store(recorder).company_ids_with_contacts()
    assert param(recorder.of("GET", "contact_emails")[0], "order") == "company_id.asc,address.asc"
    assert param(recorder.of("GET", "contact_people")[0], "order") == "company_id.asc,name.asc"


def test_ids_with_contacts_merges_both_tables():
    def responder(request):
        table = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json=[{"company_id": "c1" if table == "contact_emails"
                                          else "c2"}])
    store = make_store(Recorder(responder))
    assert store.company_ids_with_contacts() == {"c1", "c2"}
    assert store.company_ids_with_people() == {"c2"}


def test_exclusions_and_run_record():
    rows = [{"company_id": "c1", "person_key": None, "address_key": None}]
    recorder = Recorder(lambda request: httpx.Response(200, json=rows))
    store = make_store(recorder)
    assert store.exclusions() == rows
    assert param(recorder.of("GET", "contact_exclusions")[0], "select") == (
        "company_id,person_key,address_key")
    store.record_contact_run({"status": "success", "outcomes": {"ok": 1}})
    assert body(recorder.of("POST", "contact_runs")[0]) == {
        "status": "success", "outcomes": {"ok": 1}}


def test_from_env_needs_both_variables(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"):
        SupabaseContactStore.from_env()
