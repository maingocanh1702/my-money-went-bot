"""Account list render — what `/accounts` (no args) shows.

Project goal is tracking tx per account, not absolute balance. The old
`/balance` command and its rendering (running_balance / outstanding /
utilization %) was removed in favor of `_account_list_lines()`, which
only shows what a user needs to verify their onboarding:
name / type / currency / source_keys mapped.

Old tests for _balance_lines() and _format_last_tx() are gone with that code.
"""
import sheets as sh
import handlers.accounts as accounts


def test_list_empty_when_no_accounts(fake_ss):
    sh._ensure_accounts_tab()
    sh.invalidate_accounts_cache()
    lines = accounts._account_list_lines()
    assert "Chưa có account" in lines[0]


def test_list_renders_name_type_currency_slug(fake_ss):
    sh.add_account(
        account_id="bank_main", name="Ngân hàng chính", acc_type="bank",
        currency="VND", source_keys=["sepay:1903"], starting_balance=0,
    )
    sh.invalidate_accounts_cache()
    lines = accounts._account_list_lines()
    blob = "\n".join(lines)
    assert "Ngân hàng chính" in blob
    assert "(VND, bank)" in blob
    assert "bank_main" in blob
    assert "sepay:1903" in blob
    # No balance / no "Số dư" / no "Dư nợ" — those are gone.
    assert "Số dư" not in blob
    assert "Dư nợ" not in blob


def test_list_shows_unmapped_source_hint(fake_ss):
    sh.add_account(
        account_id="manual_cash", name="Cash", acc_type="cash",
        currency="VND", source_keys=[],
    )
    sh.invalidate_accounts_cache()
    lines = accounts._account_list_lines()
    blob = "\n".join(lines)
    assert "Cash" in blob
    assert "chưa map nguồn" in blob
