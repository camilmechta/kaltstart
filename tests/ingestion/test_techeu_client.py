import json
import pathlib

import httpx
import pytest

from kaltstart.ingestion.techeu_client import (
    BASE_URL, BudgetExhaustedError, FilterMismatchError, TechEuClient,
    TechEuError)

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "techeu"
ARGS = ("Switzerland", "2026-09-01", "2026-11-10")


def _load(name):
    return json.loads((FIX / name).read_text())


def _client(handler, **kwargs):
    sleeps = []
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)
    client = TechEuClient(http, sleep=sleeps.append, **kwargs)
    return client, sleeps


def _json(payload, status=200):
    return httpx.Response(status, json=payload)


def test_iter_rounds_follows_cursor():
    page1, page2 = _load("rounds_page1.json"), _load("rounds_page2.json")
    seen = []

    def handler(request):
        seen.append(request)
        return _json(page1 if len(seen) == 1 else page2)

    client, _ = _client(handler)
    rounds = list(client.iter_rounds(*ARGS))
    assert len(rounds) == 5
    assert len(seen) == 2
    for request in seen:
        params = request.url.params
        assert params["country"] == "Switzerland"
        assert params["from"] == "2026-09-01"
        assert params["to"] == "2026-11-10"
        assert params["limit"] == "100"
    assert "after" not in seen[0].url.params
    assert seen[1].url.params["after"] == page1["nextCursor"]


def test_filter_mismatch_raises():
    page = _load("rounds_page1.json")
    del page["appliedFilters"]["country"]
    client, _ = _client(lambda request: _json(page))
    produced = []
    with pytest.raises(FilterMismatchError):
        for rnd in client.iter_rounds(*ARGS):
            produced.append(rnd)
    assert produced == []


def test_waits_between_requests():
    client, sleeps = _client(lambda request: _json({"id": "c"}))
    client.get_company("a")
    assert sleeps == []
    client.get_company("b")
    assert len(sleeps) == 1
    assert 0 <= sleeps[0] <= 7.0


def test_retries_then_succeeds():
    statuses = iter([429, 503, 200])
    company = _load("company.json")

    def handler(request):
        status = next(statuses)
        return _json(company if status == 200 else {}, status)

    client, sleeps = _client(handler)
    assert client.get_company("abc") == company
    assert client.requests_made == 3
    assert 5 in sleeps and 15 in sleeps


def test_gives_up_after_three_attempts():
    calls = []

    def handler(request):
        calls.append(request)
        return _json({}, 503)

    client, _ = _client(handler)
    with pytest.raises(TechEuError):
        client.get_company("abc")
    assert len(calls) == 3

    timeouts = []

    def timeout_handler(request):
        timeouts.append(request)
        raise httpx.ConnectTimeout("timeout")

    client, _ = _client(timeout_handler)
    with pytest.raises(TechEuError):
        client.get_company("abc")
    assert len(timeouts) == 3


def test_client_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return _json({"error": "unknown country: Suisse"}, 400)

    client, _ = _client(handler)
    with pytest.raises(TechEuError, match="unknown country: Suisse"):
        list(client.iter_rounds("Suisse", "2026-09-01", "2026-11-10"))
    assert len(calls) == 1


def test_budget_exhausted():
    calls = []

    def handler(request):
        calls.append(request)
        return _json({"id": "c"})

    client, _ = _client(handler, max_requests=2)
    client.get_company("a")
    client.get_company("b")
    with pytest.raises(BudgetExhaustedError):
        client.get_company("c")
    assert len(calls) == 2


def test_fetch_changes_returns_added_and_removed():
    payload = _load("changes.json")
    payload["removed"] = ["X1", {"id": "X2"}]
    payload["nextCursor"] = None
    client, _ = _client(lambda request: _json(payload))
    added, removed = client.fetch_changes("2026-11-01")
    assert added == payload["data"]
    assert len(added) == 4
    assert removed == ["X1", "X2"]


def test_fetch_changes_stops_on_repeated_cursor():
    payload = _load("changes.json")
    payload["nextCursor"] = "same-cursor"
    calls = []

    def handler(request):
        calls.append(request)
        return _json(payload)

    client, _ = _client(handler)
    client.fetch_changes("2026-11-01")
    assert len(calls) == 2
