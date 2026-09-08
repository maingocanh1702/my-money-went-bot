"""Fixing an MCC pattern, not just adding another one.

The MCC map could only grow. `add_mcc_map` appends and refuses a duplicate, so
a pattern filed under the wrong code had no route back except opening the Google
Sheet by hand — and the bot caches the map with no TTL, so even that edit does
not take effect until something else happens to invalidate it.

Worse, nothing checked that the code *was* a code. Typing one word too many —
`TIKTOK SHOP 5611 Thoi trang` — parsed as pattern `tiktok`, MCC `SHOP`, label
`5611 Thoi trang`. `SHOP` matches no rule on any card, so those transactions
quietly earned the card's default rate instead of the fashion rate, and the
entry looked perfectly normal in the list.
"""
import pytest

import sheets as sh
import handlers.cashback as cb
from config import SHEETS as S


@pytest.fixture(autouse=True)
def _reset(fake_ss):
    sh.invalidate_cashback_caches()
    yield


@pytest.fixture
def quiet_tg(fake_ss, monkeypatch):
    """Silence the two Telegram calls the handler makes on its way out.

    Bot State has to exist: both `t()` (which reads the chat's language) and
    `set_state` go through it, so a handler test without this tab fails on the
    tab rather than on anything it meant to check.
    """
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "updated"]])

    async def _noop(*a, **k):
        return {"ok": True}

    monkeypatch.setattr(cb.tg, "send_text", _noop)
    monkeypatch.setattr(cb, "_tg_card_view", _noop)
    return _noop


def _rows():
    return sh._sheet(S.MCC_MAP).get_all_values()[1:]


def _active_patterns():
    return {m["pattern"]: m["mcc_code"] for m in sh.get_mcc_map(force_refresh=True)}


# ── re-pointing a pattern ────────────────────────────────────────────────────

def test_an_existing_pattern_moves_to_a_new_mcc():
    sh.add_mcc_map("tiktok", "SHOP", "5611 Thoi trang")
    assert sh.set_mcc_map("tiktok", "5611", "Thời trang") == "updated"

    m = _active_patterns()
    assert m["tiktok"] == "5611"
    assert "SHOP" not in m.values()


def test_re_pointing_edits_the_row_rather_than_adding_one():
    """Two rows for one pattern would make matching depend on row order."""
    sh.add_mcc_map("tiktok", "SHOP")
    before = len(_rows())
    sh.set_mcc_map("tiktok", "5611", "Thời trang")
    assert len(_rows()) == before


def test_a_pattern_that_does_not_exist_yet_is_added():
    assert sh.set_mcc_map("winmart", "5411", "Siêu thị") == "added"
    assert _active_patterns()["winmart"] == "5411"


def test_setting_the_same_values_again_changes_nothing():
    sh.set_mcc_map("winmart", "5411", "Siêu thị")
    assert sh.set_mcc_map("winmart", "5411", "Siêu thị") == "unchanged"


def test_the_label_can_be_corrected_on_its_own():
    sh.add_mcc_map("winmart", "5411", "Sieu thi")
    assert sh.set_mcc_map("winmart", "5411", "Siêu thị") == "updated"
    assert _rows()[0][2] == "Siêu thị"


# ── turning a pattern off ────────────────────────────────────────────────────

def test_deactivate_hides_the_pattern_from_matching():
    sh.add_mcc_map("winmart", "5411", "Siêu thị")
    assert sh.deactivate_mcc_map("winmart") is True
    assert "winmart" not in _active_patterns()


def test_deactivate_keeps_the_row_so_you_can_see_what_changed():
    """Soft delete, like every other removable row in this sheet."""
    sh.add_mcc_map("winmart", "5411", "Siêu thị")
    sh.deactivate_mcc_map("winmart")
    rows = _rows()
    assert len(rows) == 1
    assert rows[0][0] == "winmart" and rows[0][5].upper() == "FALSE"


def test_deactivating_something_absent_reports_it():
    assert sh.deactivate_mcc_map("nothing-here") is False


def test_the_pattern_is_matched_the_way_it_is_stored():
    """Patterns are stored lowercased and stripped of diacritics, so the user
    can type them however they like."""
    sh.add_mcc_map("winmart", "5411", "Siêu thị")
    assert sh.deactivate_mcc_map("WINMART") is True


def test_a_deactivated_pattern_can_be_added_again():
    sh.add_mcc_map("winmart", "5411", "Siêu thị")
    sh.deactivate_mcc_map("winmart")
    assert sh.set_mcc_map("winmart", "5812", "Ăn uống") == "added"
    assert _active_patterns()["winmart"] == "5812"


# ── renaming the keyword itself ──────────────────────────────────────────────

def test_a_typo_can_be_fixed_without_retyping_the_mcc():
    """The alternative is delete + re-add, which means retyping the MCC and the
    label from memory — and getting either wrong is silent."""
    sh.add_mcc_map("wimart", "5411", "Siêu thị")
    assert sh.rename_mcc_map("WIMART", "winmart") == "renamed"

    rows = _rows()
    assert len(rows) == 1
    assert rows[0][0] == "winmart"
    assert rows[0][1] == "5411" and rows[0][2] == "Siêu thị"


def test_renaming_to_the_same_spelling_is_a_no_op():
    sh.add_mcc_map("winmart", "5411", "Siêu thị")
    assert sh.rename_mcc_map("winmart", "WINMART") == "unchanged"


def test_renaming_something_absent_reports_it():
    assert sh.rename_mcc_map("nothing-here", "whatever") == "not_found"


def test_renaming_onto_an_existing_pattern_is_refused():
    """Merging two rows would have to pick one MCC to keep. That is the
    operator's decision, so the bot refuses and says so."""
    sh.add_mcc_map("winmart", "5411", "Siêu thị")
    sh.add_mcc_map("bhx", "5411", "Siêu thị")

    assert sh.rename_mcc_map("bhx", "winmart") == "conflict"
    assert sorted(_active_patterns()) == ["bhx", "winmart"], "nothing moved"


def test_a_name_freed_by_deleting_can_be_reused():
    sh.add_mcc_map("winmart", "5411", "Siêu thị")
    sh.add_mcc_map("bhx", "5411", "Siêu thị")
    sh.deactivate_mcc_map("bhx")

    assert sh.rename_mcc_map("winmart", "bhx") == "renamed"


@pytest.mark.asyncio
async def test_ren_from_the_chat(quiet_tg):
    sh.add_mcc_map("wimart", "5411", "Siêu thị")
    await cb.handle_cashback_mcc_input("ren WIMART WINMART", {})
    assert _active_patterns() == {"winmart": "5411"}


@pytest.mark.asyncio
async def test_ren_without_a_second_name_asks_again(quiet_tg):
    sh.add_mcc_map("wimart", "5411", "Siêu thị")
    await cb.handle_cashback_mcc_input("ren WIMART", {})
    assert _active_patterns() == {"wimart": "5411"}, "nothing should have changed"


# ── the input that caused the mess ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_non_numeric_mcc_is_refused(fake_ss, monkeypatch):
    """`TIKTOK SHOP 5611 Thoi trang` used to be accepted silently."""
    ws = fake_ss.add_worksheet(S.BOT_STATE)
    ws.update("A1:C1", [["chat_id", "state", "updated"]])
    sent = []

    async def _capture(text, *a, **k):
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(cb.tg, "send_text", _capture)
    monkeypatch.setattr(cb, "_tg_card_view", _capture)

    await cb.handle_cashback_mcc_input("TIKTOK SHOP 5611 Thoi trang", {})

    assert _active_patterns() == {}, "nothing should have been written"
    assert any("SHOP" in m for m in sent), "the user must be told which word was wrong"


@pytest.mark.asyncio
async def test_a_three_digit_code_is_refused(quiet_tg):
    await cb.handle_cashback_mcc_input("winmart 541", {})
    assert _active_patterns() == {}


@pytest.mark.asyncio
async def test_a_valid_line_still_adds(quiet_tg):
    await cb.handle_cashback_mcc_input("WINMART 5411 Siêu thị", {})
    assert _active_patterns()["winmart"] == "5411"


@pytest.mark.asyncio
async def test_del_turns_a_pattern_off(quiet_tg):
    sh.add_mcc_map("winmart", "5411", "Siêu thị")

    await cb.handle_cashback_mcc_input("del WINMART", {})
    assert "winmart" not in _active_patterns()
