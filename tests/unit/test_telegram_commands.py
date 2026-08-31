import pytest

from config import CHAT_ID, SHEETS as S
import main
import sheets as sh


TX_HEADER = [
    "ID", "Date", "C", "D", "E", "Description", "Type", "Amount", "Ref",
    "Cumulative", "Bucket", "Sub", "IsDaily", "Confirmed", "Month",
    "Currency", "account_id", "ledger_tx_type", "linked_tx_row",
    "ledger_applied", "account_source_key",
]


@pytest.mark.asyncio
async def test_telegram_recat_uses_transaction_month_buckets(fake_ss, monkeypatch):
    fake_ss.add_worksheet(S.TRANSACTIONS).update("A1:U1", [TX_HEADER])
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "updated"]])
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    bc.update("A2:F2", [["2026-05", "food", "🍕 Food", 0, "", "TRUE"]])
    bc.update("A3:F3", [["2026-06", "coffee", "☕ Coffee", 0, "", "TRUE"]])
    sh.invalidate_buckets_cache()

    row_num = sh.append_transaction(
        tx_date="2026-05-15T10:00:00",
        description="old month tx",
        amount=50_000,
        ref_code="RECAT_OLD_MONTH",
        month_key="2026-05",
    )

    sent = {}

    async def fake_send_with_buttons(text, buttons):
        sent["text"] = text
        sent["buttons"] = buttons
        return {"ok": True, "result": {"message_id": 1}}

    async def fake_send_text(text):
        sent["text"] = text

    monkeypatch.setattr(main.tg, "send_with_buttons", fake_send_with_buttons)
    monkeypatch.setattr(main.tg, "send_text", fake_send_text)

    await main._tg_cmd_recat(f"/recat {row_num}")

    callback_data = [btn["callback_data"] for row in sent["buttons"] for btn in row]
    assert f"p_{row_num}_food" in callback_data
    assert f"p_{row_num}_coffee" not in callback_data
    assert sh.get_state(CHAT_ID)["row_num"] == row_num


@pytest.mark.asyncio
async def test_telegram_recat_does_not_reset_when_month_has_no_buckets(fake_ss, monkeypatch):
    fake_ss.add_worksheet(S.TRANSACTIONS).update("A1:U1", [TX_HEADER])
    fake_ss.add_worksheet(S.BOT_STATE).update("A1:C1", [["chat_id", "state", "updated"]])
    bc = fake_ss.add_worksheet(S.BUDGET_CONFIG)
    bc.update("A1:F1", [["Month", "Bucket ID", "Name", "Allocated", "Daily Cap", "Active"]])
    sh.invalidate_buckets_cache()

    row_num = sh.append_transaction(
        tx_date="2026-05-15T10:00:00",
        description="old month tx",
        amount=50_000,
        ref_code="RECAT_NO_BUCKETS",
        month_key="2026-05",
    )
    sh.finalize_transaction(row_num, "food", "")

    sent = {}

    async def fake_send_text(text):
        sent["text"] = text

    monkeypatch.setattr(main.tg, "send_text", fake_send_text)

    await main._tg_cmd_recat(f"/recat {row_num}")

    row = sh.get_transaction_row(row_num)
    assert "Không có category active" in sent["text"]
    assert row[10] == "food"
    assert row[13] == "TRUE"
