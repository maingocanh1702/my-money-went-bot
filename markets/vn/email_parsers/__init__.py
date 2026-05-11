"""VN bank email parsers — plugin registry (Gap 2).

Importing this package auto-imports every parser module so the
`@register_parser('BANK')` decorators fire and populate `PARSERS`.

Add a new bank: create a sibling module, decorate the class with
`@register_parser('XYZ')`, add the module name to the
`_AUTO_IMPORT_MODULES` list below. No central wiring elsewhere.

Hard invariants (enforced by `.importlinter` `parsers-are-pure`):
  - this package MUST NOT import `core.db`
  - this package MUST NOT import `core.messenger`
  - parsers only consume `InboundEmail`, produce `CanonicalTx`
"""

from __future__ import annotations

from importlib import import_module

# Modules to auto-import for side-effect registration. Listed explicitly
# (no globbing) so the import order is deterministic — relevant if two
# parsers can_parse the same email and the dispatcher picks the first
# match in registration order.
_AUTO_IMPORT_MODULES: list[str] = [
    "markets.vn.email_parsers.tcb",
    "markets.vn.email_parsers.mb",
    "markets.vn.email_parsers.acb",
    "markets.vn.email_parsers.sacombank",
    "markets.vn.email_parsers.bidv",
    "markets.vn.email_parsers.cake",
]

for _mod in _AUTO_IMPORT_MODULES:
    import_module(_mod)

from .base import (  # noqa: E402 — must follow side-effect imports
    PARSERS,
    BankEmailParser,
    InboundEmail,
    find_parser,
    get_parser,
    register_parser,
)

__all__ = [
    "PARSERS",
    "BankEmailParser",
    "InboundEmail",
    "find_parser",
    "get_parser",
    "register_parser",
]
