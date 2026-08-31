"""Handlers package — channel-agnostic command + callback entry points.

Each submodule exposes async functions used by the channel dispatchers
(Telegram webhook, Zalo Bot events). Modules are imported lazily by callers;
this package's only job is to be the import root.
"""

from __future__ import annotations
