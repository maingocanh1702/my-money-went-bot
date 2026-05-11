"""Market-specific implementations for MyMoneyWent.

Subpackages:
- markets.vn       — Vietnam market (SePay, VN bank email, VietQR, Zalo, VND tiers)
- markets.global_  — Global market (Plaid/TrueLayer/Tink, Stripe/Shopify/Etsy, USD tiers)

Naming note: the global market package is `global_` (trailing underscore) because
`global` is a Python reserved keyword. Architecture intent per ADR-0001 is
unchanged — the directory `markets/global_/` represents the global market.

Boundary rule (per ADR-0001):
- core/ MUST NOT import from markets/
- markets/vn/ MUST NOT import from markets/global_/
- markets/global_/ MUST NOT import from markets/vn/

Enforced by .importlinter.
"""
