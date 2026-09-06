"""Regression tests for the 2026-09-05 external code audit.

Each test pins a finding that was verified against the code and, for the
SePay contract, against SePay's own documentation:

  F-01  SePay authenticates with "Authorization: Apikey <key>" — a header.
        The bot only read the body, so every real delivery was rejected once
        SEPAY_SECRET was set.
  F-02  SePay only treats 200/201 + {"success": true} as delivered. The bot
        returned {"ok": true}, so every delivery was retried.
  F-07  `buttons` was bound only when the Telegram user was idle; a mid-flow
        Telegram user silently lost the Zalo picker (UnboundLocalError,
        swallowed by a broad except).
  F-08  The Zalo MCC-learn picker referenced `rules` and `CASHBACK_MCC_EMOJI`,
        neither of which exist in handlers/sepay.py — NameError on every call,
        swallowed by the same kind of except.
"""
import pytest

import sheets as sh
from handlers import sepay

from tests.unit.test_zalo_pending_queue import (  # noqa: F401 — fixtures
    zalo_world, _payload, _seed_unconfirmed_row, ZALO_KEY,
)


# ─── F-01 / F-02: SePay HTTP contract ────────────────────────────────────


@pytest.fixture
def sepay_http(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import main

    calls = []

    async def record(payload, *, authenticated=False):
        calls.append({"payload": payload, "authenticated": authenticated})

    monkeypatch.setattr(main, "SEPAY_SECRET", "sepay-secret", raising=False)
    monkeypatch.setattr(sepay, "SEPAY_SECRET", "sepay-secret")
    monkeypatch.setattr(main, "handle_sepay_webhook", record)

    async def post(headers=None, json=None):
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            return await client.post("/webhook", json=json or {"transferAmount": 1000}, headers=headers or {})

    post.calls = calls
    return post


@pytest.mark.asyncio
async def test_sepay_accepts_the_documented_apikey_header(sepay_http):
    response = await sepay_http(headers={"Authorization": "Apikey sepay-secret"})

    assert response.status_code == 200
    assert response.json()["success"] is True          # F-02: the provider's contract
    assert sepay_http.calls and sepay_http.calls[0]["authenticated"] is True


@pytest.mark.asyncio
async def test_sepay_header_scheme_is_case_insensitive(sepay_http):
    response = await sepay_http(headers={"Authorization": "apikey sepay-secret"})
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [
    {},                                                   # nothing at all
    {"Authorization": "Apikey wrong"},                    # wrong key
    {"Authorization": "Bearer sepay-secret"},             # right key, wrong scheme
    {"Authorization": "sepay-secret"},                    # no scheme
])
async def test_sepay_rejects_missing_wrong_or_misschemed_credentials(sepay_http, headers):
    response = await sepay_http(headers=headers)

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert sepay_http.calls == []


@pytest.mark.asyncio
async def test_sepay_body_key_still_works_for_local_tooling(sepay_http):
    """scripts/sim_webhook.py posts the key in the body; keep that path alive."""
    response = await sepay_http(json={"transferAmount": 1000, "apikey": "sepay-secret"})
    assert response.status_code == 200


def test_secret_checker_reads_the_authorization_header(monkeypatch):
    monkeypatch.setattr(sepay, "SEPAY_SECRET", "sepay-secret")
    assert sepay.has_valid_sepay_secret({}, authorization="Apikey sepay-secret")
    assert not sepay.has_valid_sepay_secret({}, authorization="Apikey nope")
    assert not sepay.has_valid_sepay_secret({}, authorization="Bearer sepay-secret")
    assert not sepay.has_valid_sepay_secret({}, authorization=None)


@pytest.mark.asyncio
async def test_boundary_authenticated_delivery_is_not_rechecked_against_the_body(monkeypatch, capsys):
    """After the header check passes, the handler must not demand a body key too —
    SePay puts nothing in the body, so that second check rejected every delivery."""
    monkeypatch.setattr(sepay, "SEPAY_SECRET", "sepay-secret")

    await sepay.handle_sepay_webhook({"data": {}}, authenticated=True)

    out = capsys.readouterr().out
    assert "rejected: invalid secret" not in out
    assert "[sepay] incoming" in out


# ─── F-07: Zalo picker survives a mid-flow Telegram user ─────────────────


@pytest.mark.asyncio
async def test_zalo_picker_is_sent_even_when_telegram_user_is_mid_flow(zalo_world):
    # Telegram side is inside a critical text step → the tx is queued for
    # Telegram. The Zalo side is idle and must still get its numbered picker.
    sh.set_state(sepay.CHAT_ID, {"step": "await_manage_amount", "edit_bucket_id": "food"})

    await sepay.handle_sepay_webhook(_payload(ref="F07"))

    zalo_msgs = zalo_world.sent["zalo"]
    assert any("Khoản này thuộc mục nào" in m for m in zalo_msgs), \
        f"Zalo picker was dropped when Telegram was mid-flow; zalo got: {zalo_msgs}"
    assert (sh.get_state(ZALO_KEY) or {}).get("step") == "await_zalo_parent"


# ─── F-08: Zalo MCC-learn picker actually renders ────────────────────────


@pytest.mark.asyncio
async def test_zalo_cashback_learn_picker_renders_choices(zalo_world, monkeypatch):
    from handlers import cashback

    _seed_unconfirmed_row(row_num=2, amount=120000, desc="UNKNOWN MERCHANT 77")
    monkeypatch.setattr(sh, "is_mcc_excluded", lambda _d: False)
    monkeypatch.setattr(sh, "match_mcc", lambda _d: None)
    monkeypatch.setattr(sh, "find_account_by_id", lambda _a: {"name": "Demo Card"})
    monkeypatch.setattr(
        cashback, "_get_mcc_choices",
        lambda _account_id: [("5411", "🛒 Supermarket"), ("5812", "🍽 Dining")],
    )

    await sepay._ask_cashback_learn("demo_card", 2)

    zalo_msgs = zalo_world.sent["zalo"]
    assert any("1. 🛒 Supermarket" in m and "2. 🍽 Dining" in m for m in zalo_msgs), \
        f"MCC picker never reached Zalo; zalo got: {zalo_msgs}"
    state = sh.get_state(ZALO_KEY) or {}
    assert state.get("step") == "await_zalo_cb_learn_mcc"
    assert state.get("rules") == [
        {"mcc": "5411", "name": "🛒 Supermarket"},
        {"mcc": "5812", "name": "🍽 Dining"},
    ]
