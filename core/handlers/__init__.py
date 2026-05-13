"""Core handlers — multi-tenant feature handlers (Phase 2+).

Replaces legacy single-tenant `handlers/*.py`. F02 strangler cutover will
delete the legacy modules; until then both trees coexist.

Per ADR-0001, handlers MAY import from `markets/*` to bridge core/business
logic ↔ market-specific adapters (the import boundary forbids core →
markets, not handlers → markets).
"""
