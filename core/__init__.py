"""Market-agnostic foundation for MyMoneyWent.

This package MUST NOT import from `markets.*`. Per ADR-0001, adapter
dispatch happens at exactly one boundary (`core/tenant_context.py`).

Enforcement: `.importlinter` config + CI `lint-imports` step.
See: docs/adr/0001-monorepo-not-split-repos.md
"""
