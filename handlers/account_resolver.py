"""handlers/account_resolver.py — map an incoming payload to an account.

Three statuses (plan §4.2):
- matched          : we extracted an identifier and it exists in source_keys
                     of an active account → write account_id directly.
- new_identifier   : we extracted an identifier but no account owns it yet
                     → caller pings the user to onboard a new account.
- no_identifier    : no identifier could be extracted from the payload
                     → caller writes the tx with empty account_id (silent).

`source_key` format: f"{source}:{identifier_normalized}"
   - source ∈ {"sepay", "email_tcb", "email_cake", "email_hangseng"}
   - identifier_normalized: lowercased, whitespace stripped.

We deliberately do NOT auto-resolve "default" identifiers (e.g. Cake's
single-account assumption) here — the resolver returns no_identifier and
the bot lets the existing flow run; the user adds the source_key once
through onboarding and from then on it matches.

The resolver is sync. Heavy I/O (sheet reads via get_active_accounts) is
already cached in sheets.py, so this is cheap to call per webhook.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import sheets as sh


ResolveStatus = Literal["matched", "new_identifier", "no_identifier"]


@dataclass
class ResolveResult:
    status:      ResolveStatus
    account_id:  Optional[str] = None   # set when status == "matched"
    identifier:  Optional[str] = None   # raw extracted, e.g. "1903xxxxxxx888"
    source_key:  Optional[str] = None   # full "{source}:{identifier}"


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _build_source_key(source: str, identifier: str) -> str:
    return f"{source}:{identifier.strip().lower()}"


def _extract_identifier(source: str, payload: dict) -> str | None:
    """Pull the bank-side identifier out of the payload, per source.

    Returns the raw (unnormalized) identifier string, or None if the
    payload didn't carry one. The source_key uses the lowercase form.
    """
    if source == "sepay":
        # SePay always sends accountNumber (sometimes via subAccount on
        # virtual-account integrations). gateway is too coarse — multiple
        # accounts share one gateway code.
        for k in ("accountNumber", "account_number", "subAccount", "sub_account"):
            v = payload.get(k)
            if v:
                return str(v).strip()
        # data nested form
        data = payload.get("data") or {}
        for k in ("accountNumber", "account_number", "subAccount", "sub_account"):
            v = data.get(k)
            if v:
                return str(v).strip()
        return None

    if source == "email_tcb":
        # The email parser stuffs masked account into _account_hint
        v = payload.get("_account_hint")
        return str(v).strip() if v else None

    if source == "email_cake":
        # Cake email body has no per-account number → caller falls back to
        # a constant "default" hint, which a user-onboarded source_key will
        # carry into the matched path.
        v = payload.get("_account_hint")
        return str(v).strip() if v else None

    if source == "email_hangseng":
        v = payload.get("_account_hint")
        return str(v).strip() if v else None

    return None


def _detect_source(payload: dict) -> str:
    """Determine which extractor to use. Email parsers stamp `_source`;
    SePay payloads don't, so `_source` absent → sepay.
    """
    src = payload.get("_source") or ""
    if src.startswith("email_"):
        return src
    return "sepay"


def resolve_account(payload: dict, source: str | None = None) -> ResolveResult:
    """Resolve an incoming payload to an account.

    `source` is optional; if omitted we infer from `payload["_source"]`.
    """
    src = source or _detect_source(payload)
    identifier = _extract_identifier(src, payload)
    if not identifier:
        return ResolveResult(status="no_identifier")

    source_key = _build_source_key(src, identifier)
    acc = sh.find_account_by_source_key(source_key)
    if acc:
        return ResolveResult(
            status="matched",
            account_id=acc["id"],
            identifier=identifier,
            source_key=source_key,
        )
    return ResolveResult(
        status="new_identifier",
        identifier=identifier,
        source_key=source_key,
    )
