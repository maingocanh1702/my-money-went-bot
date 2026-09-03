"""Phase 1 — account resolver unit tests."""
import pytest
import sheets as sh
from handlers.account_resolver import resolve_account, ResolveResult
from config import SHEETS as S


def _seed_account(fake_ss, account_id, source_keys, acc_type="bank", currency="VND"):
    sh._ensure_accounts_tab()
    ok = sh.add_account(
        account_id=account_id,
        name=account_id,
        acc_type=acc_type,
        currency=currency,
        source_keys=source_keys,
        starting_balance=0,
    )
    assert ok, f"failed to seed {account_id}"
    sh.invalidate_accounts_cache()


def test_resolver_no_identifier_when_payload_empty(fake_ss):
    sh._ensure_accounts_tab()
    res = resolve_account({})
    assert res.status == "no_identifier"
    assert res.account_id is None


def test_resolver_matched_sepay(fake_ss):
    _seed_account(fake_ss, "tcb_main", ["sepay:1903999888"])
    res = resolve_account({"accountNumber": "1903999888"})
    assert res.status == "matched"
    assert res.account_id == "tcb_main"
    assert res.identifier == "1903999888"
    assert res.source_key == "sepay:1903999888"


def test_resolver_matched_via_subaccount_fallback(fake_ss):
    _seed_account(fake_ss, "tcb_va", ["sepay:VA001"])
    res = resolve_account({"subAccount": "VA001"})
    assert res.status == "matched"
    assert res.account_id == "tcb_va"


def test_resolver_new_identifier_when_unknown(fake_ss):
    _seed_account(fake_ss, "tcb_main", ["sepay:1903999888"])
    res = resolve_account({"accountNumber": "9999"})
    assert res.status == "new_identifier"
    assert res.identifier == "9999"
    assert res.source_key == "sepay:9999"
    assert res.account_id is None


def test_resolver_email_tcb(fake_ss):
    _seed_account(fake_ss, "tcb_main", ["email_tcb:****1234"])
    res = resolve_account({"_source": "email_tcb", "_account_hint": "****1234"})
    assert res.status == "matched"
    assert res.account_id == "tcb_main"


def test_resolver_email_cake_bank_hint(fake_ss):
    """Bank format → hint 'cake_main' → matches account with that source_key."""
    _seed_account(fake_ss, "cake_main", ["email_cake:cake_main"])
    res = resolve_account({"_source": "email_cake", "_account_hint": "cake_main"})
    assert res.status == "matched"
    assert res.account_id == "cake_main"


def test_resolver_email_cake_cc_hint(fake_ss):
    """Format 2 (Thanh toán POS) → hint 'cake_cc' → separate from cake_main."""
    _seed_account(fake_ss, "cake_visa", ["email_cake:cake_cc"], acc_type="credit")
    res = resolve_account({"_source": "email_cake", "_account_hint": "cake_cc"})
    assert res.status == "matched"
    assert res.account_id == "cake_visa"


def test_resolver_email_hangseng(fake_ss):
    _seed_account(fake_ss, "hsbc_main",
                  ["email_hangseng:123-456999-789"], currency="HKD")
    res = resolve_account({"_source": "email_hangseng", "_account_hint": "123-456999-789"})
    assert res.status == "matched"
    assert res.account_id == "hsbc_main"


def test_resolver_multiple_source_keys_match_any(fake_ss):
    _seed_account(fake_ss, "tcb_main",
                  ["sepay:1903999888", "email_tcb:****8888"])
    # Match via sepay
    res1 = resolve_account({"accountNumber": "1903999888"})
    assert res1.account_id == "tcb_main"
    # Match via email
    res2 = resolve_account({"_source": "email_tcb", "_account_hint": "****8888"})
    assert res2.account_id == "tcb_main"


def test_resolver_identifier_normalized_lowercase(fake_ss):
    _seed_account(fake_ss, "tcb_main", ["sepay:abc123"])
    res = resolve_account({"accountNumber": "ABC123"})
    assert res.status == "matched"  # source_key normalized to lowercase
