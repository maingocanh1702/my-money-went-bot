"""i18n hygiene + user-visible prompt regressions (audit 2026-08-25 round 2)."""
import pytest

from i18n.vi import STRINGS as VI
from i18n.en import STRINGS as EN


def test_vi_en_key_parity():
    """Every key must exist in BOTH languages — t() falls back silently, so a
    missing EN key means a Vietnamese string leaks into the English UI."""
    assert set(VI) == set(EN), (
        f"missing in en: {sorted(set(VI) - set(EN))}; "
        f"missing in vi: {sorted(set(EN) - set(VI))}"
    )


def test_no_literal_backslash_n_in_strings():
    """`\\n` typed as two characters renders literally in chat (the old
    ac.unmapped bug)."""
    for lang, strings in (("vi", VI), ("en", EN)):
        for key, val in strings.items():
            assert "\\n" not in val, f"{lang}:{key} contains a literal backslash-n"


def test_help_key_exists_and_lists_commands():
    for strings in (VI, EN):
        text = strings["help"]
        for cmd in ("/report", "/today", "/manage", "/pending", "/recat", "/cashback"):
            assert cmd in text, f"help text missing {cmd}"


@pytest.mark.asyncio
async def test_zalo_cashback_rule_field_prompt_is_translated(fake_ss, monkeypatch):
    """Zalo rule-edit used to send the raw i18n KEY ('cb.rf_name') to the
    user instead of the translated prompt."""
    from config import SHEETS as S
    import handlers.cashback as cashback
    import sheets as sh

    ws_st = fake_ss.add_worksheet(S.BOT_STATE)
    ws_st.update("A1:C1", [["chat_id", "state", "updated"]])

    import i18n.core as i18n_core
    monkeypatch.setattr(i18n_core, "_lang_cache", "vi")

    sent = []

    async def _send(chat_id, text):
        sent.append(text)

    monkeypatch.setattr(cashback, "_zalo_send", _send)

    state = {"step": "zalo_cashback_rule_menu", "account_id": "cake_cc",
             "rule_id": "cake_cc_5411"}
    await cashback.zalo_handle_rule_menu("chat-1", "1", state, "zalo:chat-1")

    assert sent, "no prompt sent"
    assert "cb.rf_" not in sent[-1], f"raw i18n key leaked to user: {sent[-1]!r}"
    assert "Nhập tên" in sent[-1]
