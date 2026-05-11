"""VN-market transaction capture pipeline (SePay webhook + email inbound).

This package owns the side-effect layer for VN transaction capture:
- Resolve user from webhook token / inbound-email mailbox.
- Persist `CanonicalTx` (from parsers) into Postgres.
- Trigger downstream messenger replies.

Parsers in `markets.vn.email_parsers` are PURE — they don't import
this package. Side effects only live here.
"""
