"""SupabaseStore driven offline: the supabase client talks to an httpx.MockTransport."""

import json
from urllib.parse import unquote

import httpx
from supabase import ClientOptions, create_client

from kaltstart.ingestion.store import WATERMARK_COMMANDS
from kaltstart.ingestion.supabase_store import SupabaseStore

FAKE_URL = "http://localhost:54321"
FAKE_KEY = "test-key"


class Recorder:
    """Records every request and answers with `responder(request)`."""

    def __init__(self, responder=None):
        self.requests: list[httpx.Request] = []
        self.responder = responder or (lambda request: httpx.Response(200, json=[]))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responder(request)

    def of(self, method: str, table: str) -> list[httpx.Request]:
        return [r for r in self.requests
                if r.method == method and r.url.path == f"/rest/v1/{table}"]


def make_store(recorder: Recorder) -> SupabaseStore:
    http = httpx.Client(transport=httpx.MockTransport(recorder))
    client = create_client(FAKE_URL, FAKE_KEY, options=ClientOptions(httpx_client=http))
    return SupabaseStore(client)


def body(request: httpx.Request):
    return json.loads(request.content)


def in_filter_ids(request: httpx.Request) -> list[str]:
    value = unquote(request.url.params["id"])
    assert value.startswith("in.(") and value.endswith(")")
    return value[4:-1].split(",")


def company_row(cid):
    return {"id": cid, "name": cid, "country": "Switzerland", "city_raw": None,
            "city": None, "region": None, "sectors": [], "techeu_url": "https://x"}


def test_upsert_companies_sends_only_company_columns_and_merges():
    recorder = Recorder()
    store = make_store(recorder)
    store.upsert_companies([company_row("c1")])
    (request,) = recorder.of("POST", "companies")
    assert "resolution=merge-duplicates" in request.headers["prefer"]
    (row,) = body(request)
    assert set(row) == set(company_row("c1")) | {"updated_at"}
    for column in ("website", "description", "founded", "details_fetched_at"):
        assert column not in row


def test_upserts_are_split_in_batches_of_500():
    recorder = Recorder()
    store = make_store(recorder)
    store.upsert_companies([company_row(f"c{i}") for i in range(1201)])
    sizes = [len(body(r)) for r in recorder.of("POST", "companies")]
    assert sizes == [500, 500, 201]


def test_empty_upserts_send_no_request():
    recorder = Recorder()
    store = make_store(recorder)
    store.upsert_raw_rounds([])
    store.upsert_companies([])
    store.upsert_rounds([])
    assert recorder.requests == []


def test_all_raw_rounds_pages_past_1000_rows():
    rows = [{"id": f"r{i:04d}", "payload": {"id": f"r{i:04d}"}} for i in range(2300)]

    def responder(request):
        params = request.url.params
        start = int(params.get("offset", 0))
        limit = int(params.get("limit", 1000))
        return httpx.Response(200, json=rows[start:start + limit])

    recorder = Recorder(responder)
    payloads = make_store(recorder).all_raw_rounds()
    assert [p["id"] for p in payloads] == [r["id"] for r in rows]
    assert len(recorder.of("GET", "raw_rounds")) == 3


def test_delete_rounds_uses_batches_of_100_and_counts_deleted_rows():
    ids = [f"{i:036d}" for i in range(250)]

    def responder(request):
        if request.url.path.endswith("/rounds"):
            return httpx.Response(200, json=[{"id": i} for i in in_filter_ids(request)])
        return httpx.Response(200, json=[])

    recorder = Recorder(responder)
    deleted = make_store(recorder).delete_rounds(ids)
    assert deleted == 250
    for table in ("rounds", "raw_rounds"):
        batches = [in_filter_ids(r) for r in recorder.of("DELETE", table)]
        assert [len(b) for b in batches] == [100, 100, 50]
        assert [i for b in batches for i in b] == ids


def test_last_successful_run_filters_on_status_and_watermark_commands():
    recorder = Recorder(lambda request: httpx.Response(
        200, json=[{"started_at": "2026-11-10T03:00:00+00:00"}]))
    started = make_store(recorder).last_successful_run_started_at()
    assert started == "2026-11-10T03:00:00+00:00"
    (request,) = recorder.of("GET", "sync_runs")
    params = request.url.params
    assert params["status"] == "eq.success"
    commands = unquote(params["command"])
    assert commands == f"in.({','.join(WATERMARK_COMMANDS)})"
    assert set(WATERMARK_COMMANDS) == {"backfill", "sync"}
    assert params["order"] == "started_at.desc"
    assert params["limit"] == "1"


def test_last_successful_run_is_none_without_rows():
    assert make_store(Recorder()).last_successful_run_started_at() is None


def test_counts_parses_head_content_range():
    totals = {"raw_rounds": 7, "companies": 3, "rounds": 12}

    def responder(request):
        table = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(
            200, json=[], headers={"content-range": f"0-0/{totals[table]}"})

    recorder = Recorder(responder)
    assert make_store(recorder).counts() == totals
    assert all(r.method == "HEAD" for r in recorder.requests)
    assert all(r.headers["prefer"] == "count=exact" for r in recorder.requests)


def test_counts_of_empty_tables_are_zero():
    recorder = Recorder(lambda request: httpx.Response(
        200, json=[], headers={"content-range": "*/0"}))
    assert make_store(recorder).counts() == {
        "raw_rounds": 0, "companies": 0, "rounds": 0}
