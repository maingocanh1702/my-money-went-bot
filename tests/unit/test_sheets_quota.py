"""Regression coverage for the Google Sheets quota safeguards."""

from unittest.mock import Mock

from google.auth.credentials import AnonymousCredentials
from gspread.exceptions import APIError
from gspread.http_client import HTTPClient

import sheets as sh
from config import SHEETS as S


def _api_error(status: int) -> APIError:
    response = Mock()
    response.status_code = status
    response.json.return_value = {
        "error": {"code": status, "message": "simulated Google API error"}
    }
    return APIError(response)


def test_quota_client_retries_429_with_bounded_backoff(monkeypatch):
    calls = []
    sleeps = []

    def request(_self, *_args, **_kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise _api_error(429)
        return "ok"

    monkeypatch.setattr(HTTPClient, "request", request)
    monkeypatch.setattr(sh.time, "sleep", sleeps.append)

    client = sh.QuotaBackoffHTTPClient(AnonymousCredentials())

    assert client.request("GET", "https://example.invalid") == "ok"
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_quota_client_does_not_retry_non_quota_errors(monkeypatch):
    calls = []

    def request(_self, *_args, **_kwargs):
        calls.append(1)
        raise _api_error(403)

    monkeypatch.setattr(HTTPClient, "request", request)
    client = sh.QuotaBackoffHTTPClient(AnonymousCredentials())

    try:
        client.request("GET", "https://example.invalid")
    except APIError as error:
        assert error.code == 403
    else:
        raise AssertionError("non-quota API errors must not be retried")
    assert len(calls) == 1


def test_state_writes_reuse_cached_row_without_extra_sheet_reads(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C2", [["chat_id", "state", "updated"], ["owner", '{"step": "old"}', "t0"]])

    reads = {"count": 0}
    original_get_all_values = ws.get_all_values

    def counting_get_all_values():
        reads["count"] += 1
        return original_get_all_values()

    ws.get_all_values = counting_get_all_values

    assert sh.get_state("owner") == {"step": "old"}
    sh.set_state("owner", {"step": "new"})
    sh.clear_state("owner")

    assert reads["count"] == 1
    assert sh.get_state("owner") == {}


def test_new_state_is_located_once_then_updates_without_rereading(fake_ss):
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "updated"]])

    reads = {"count": 0}
    original_get_all_values = ws.get_all_values

    def counting_get_all_values():
        reads["count"] += 1
        return original_get_all_values()

    ws.get_all_values = counting_get_all_values

    sh.set_state("owner", {"step": "first"})
    sh.set_state("owner", {"step": "second"})

    assert reads["count"] == 1
    assert sh.get_state("owner") == {"step": "second"}
