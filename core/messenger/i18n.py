"""Compat shim for the W0.4 messenger-local i18n stub.

The real i18n module now lives at the top-level `i18n/` package
(see docs/features/feature-i18n.md). This file remains so existing
`from core.messenger import i18n` imports keep working with the
legacy `t(key, locale, **params)` signature.

Prefer importing the top-level module in new code:

    from i18n import t  # signature: t(locale, key, **kwargs)
"""

from __future__ import annotations

from i18n import PACKS
from i18n import t as _t_top


def t(key: str, locale: str = "vi", **params: object) -> str:
    """Legacy key-first signature — delegates to top-level `i18n.t`."""
    # Top-level returns '[MISSING: key]' for unknowns; preserve legacy
    # '??key??' loud marker so existing tests + log greps still match.
    if key not in PACKS.get(locale, {}) and key not in PACKS.get("vi", {}):
        return f"??{key}??"
    return _t_top(locale, key, **params)


def reset_cache() -> None:
    """No-op: top-level i18n loads at import time, nothing to reset."""


__all__ = ["reset_cache", "t"]
