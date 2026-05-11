"""SePay webhook → CanonicalTx → DB (Gap 3).

Entrypoint: FastAPI route `POST /webhooks/sepay/{token}` mounted by
`main.py` (W0.6+). Body shape per SePay docs — a single transfer:

    {
      "id": 12345,
      "gateway": "TCB",
      "transactionDate": "2026-05-11 09:42:13",
      "accountNumber": "0123456789",
      "subAccount": null,
      "transferType": "in",          # 'in' | 'out'
      "transferAmount": 50000,
      "accumulated": ...,
      "code": null,
      "content": "NAP TIEN",
      "referenceCode": "FT26..."
    }

Security:
  - Token compared by SHA-256 hash. Bad token → 200 OK (silent), so the
    response never confirms or denies a token's validity.
  - Webhook bodies don't carry user identity directly — the URL token
    resolves to user_id via `webhook_tokens` lookup.

Tenant isolation:
  - Tx insert uses the resolved user_id; `tenant_context.set_tenant()`
    is also called so logging + Sentry tag the request correctly.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal

from core import db, tenant_context
from core.canonical_tx import CanonicalTx
from core.logging import get_logger

from .webhook_tokens import resolve_token

log = get_logger(__name__, component="sepay_webhook")


def _to_canonical(payload: dict[str, Any]) -> CanonicalTx:
    """Parse SePay JSON → CanonicalTx. Pure — no DB."""
    direction_raw = (payload.get("transferType") or "").lower()
    if direction_raw not in ("in", "out"):
        raise ValueError(f"sepay: bad transferType={direction_raw!r}")
    direction: Literal["in", "out"] = "in" if direction_raw == "in" else "out"
    amount = int(payload.get("transferAmount") or 0)
    if amount <= 0:
        raise ValueError(f"sepay: bad transferAmount={amount!r}")

    raw_date = payload.get("transactionDate") or ""
    try:
        tx_date = datetime.fromisoformat(raw_date.replace(" ", "T"))
    except ValueError as exc:
        raise ValueError(f"sepay: bad transactionDate={raw_date!r}") from exc

    bank = (payload.get("gateway") or "").upper() or "UNKNOWN"
    # SePay's own event id (`id` in payload). When SePay omits
    # `referenceCode`, this is the only field that distinguishes two
    # otherwise-identical events (e.g. two same-amount deposits in the
    # same second). Always persist so the dedupe fallback can use it.
    provider_event_id = str(payload.get("id") or "")
    return CanonicalTx(
        source="sepay",
        bank=bank,
        direction=direction,
        amount=amount,
        tx_date=tx_date,
        ref_code=str(payload.get("referenceCode") or ""),
        description=str(payload.get("content") or ""),
        last4=str(payload.get("accountNumber") or "")[-4:],
        provider_event_id=provider_event_id,
    )


def _content_hash_ref_code(user_id: int, tx: CanonicalTx) -> str:
    """Last-resort content hash for dedupe when no provider identifier exists.

    Codex P1 round 2: two distinct events that happen to share user +
    tx_date + amount + direction + bank + last4 (e.g. two same-amount
    deposits in the same second) WILL collide here — that risk is
    acceptable only as a last fallback. Prefer `provider_event_id` when
    present (see `_persist`).

    Prefix `hash-` marks these as content-derived so queries / audits can
    distinguish them from real bank ref_codes and from provider-id ref_codes.
    """
    key = f"{user_id}:{tx.tx_date.isoformat()}:{tx.amount}:{tx.direction}:{tx.bank}:{tx.last4}"
    return "hash-" + hashlib.sha256(key.encode()).hexdigest()[:24]


async def _persist(user_id: int, tx: CanonicalTx, month_key: str) -> None:
    # Idempotency requires a non-null ref_code: Postgres treats NULL != NULL
    # inside UNIQUE constraints, so storing an empty ref_code as NULL would
    # let every retry insert a duplicate row.
    #
    # Layered fallback when the bank's `ref_code` is empty:
    #   1. Bank's ref_code (most authoritative; always used when present).
    #   2. Provider's event id (SePay `id`, etc.) — uniquely identifies the
    #      logical event; retries share it, distinct events don't. ALWAYS
    #      hashed to a fixed-length form so the result fits the
    #      `transactions.ref_code VARCHAR(64)` schema bound regardless of
    #      upstream payload anomalies (Codex P2 round 3).
    #   3. Content hash — last resort. Carries collision risk between two
    #      same-amount events in the same second, so only used when both
    #      `ref_code` AND `provider_event_id` are empty.
    if tx.ref_code:
        ref_code = tx.ref_code
    elif tx.provider_event_id:
        # SHA-256 truncated to 24 hex chars (96 bits) — collision-resistant
        # for the dedupe scope of a single user. Full ref_code:
        # `{source}-id-{24-hex}` ≈ 33 chars, safely under VARCHAR(64).
        digest = hashlib.sha256(tx.provider_event_id.encode()).hexdigest()[:24]
        ref_code = f"{tx.source}-id-{digest}"
    else:
        ref_code = _content_hash_ref_code(user_id, tx)

    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO transactions
                (user_id, tx_date, description, direction, amount,
                 ref_code, source, month_key)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id, ref_code) DO NOTHING;
            """,
            user_id,
            tx.tx_date,
            tx.description,
            tx.direction,
            tx.amount,
            ref_code,
            tx.source,
            month_key,
        )


async def handle_sepay_webhook(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Process one SePay webhook delivery.

    Always returns `{"ok": True}` — bad tokens / bad payloads are logged
    and silently accepted so SePay's retry behaviour doesn't pile up
    (and so attackers can't probe token validity through response
    differences). Real errors raise to Sentry via the logger.
    """
    user_id = await resolve_token(token, kind="sepay")
    if user_id is None:
        log.info("sepay.webhook.token_invalid", token_len=len(token))
        return {"ok": True}

    tenant_context.set_tenant(user_id)
    try:
        tx = _to_canonical(payload)
    except ValueError as exc:
        log.warning("sepay.webhook.parse_failed", reason=str(exc))
        return {"ok": True}

    month_key = tx.tx_date.strftime("%Y-%m")
    await _persist(user_id, tx, month_key)
    log.info(
        "sepay.webhook.persisted",
        bank=tx.bank,
        direction=tx.direction,
        amount=tx.amount,
        ref_code=tx.ref_code or None,
    )
    return {"ok": True}
