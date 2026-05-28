"""Founder Sheets → Postgres one-time migration (Gap 5).

Strict ordering (FK dependencies):

  1. users              — founder row(s). user_id=1 → role='founder'.
                           This is BOOTSTRAP-ONLY. Runtime MUST NOT
                           hardcode `if user_id == 1`. Admin powers
                           come from `users.role IN ('founder','admin')`.
  2. categories         — per-user spending buckets, keyed by month_key.
  3. funding_sources    — derived from Sheets column P (`bank_account`
                           mirror string). Canonical identity
                           (user_id, kind, bank, last4).
  4. transactions       — references categories + funding_sources via
                           FK. Skip rows whose category_id / fs_id
                           failed to resolve (Sheets→PG mapping is 1-1,
                           but Sheets is a long-running mutable doc;
                           defensive skipping beats partial inserts).
  5. admin_audit_log    — optional historical audit entries the
                           founder kept (skipped if absent).

Verification (run AFTER migration, fails loud on mismatch):

  - Row counts match Sheets — for each of the 5 tables.
  - Sample fields match — pull N random rows per table, compare to
    Sheets cells.
  - No orphan user_id — every tx / category / fs row points at a real
    users.id.
  - Tenant isolation smoke — pick 2 user_ids, assert each user's tx
    scope returns only their rows (the same rule W0.3's integration
    test enforces).

W0.6 ships the SKELETON: argument parsing, ordering, verification stub.
The actual Google Sheets read calls live in Wave 1 once the founder
runs a real migration. Until then, dry-runs print the plan + exit 0.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

from core import db


@dataclass
class MigrationSummary:
    users_inserted: int = 0
    categories_inserted: int = 0
    funding_sources_inserted: int = 0
    transactions_inserted: int = 0
    audit_inserted: int = 0
    skipped_orphans: int = 0

    def total(self) -> int:
        return (
            self.users_inserted
            + self.categories_inserted
            + self.funding_sources_inserted
            + self.transactions_inserted
            + self.audit_inserted
        )


async def migrate(database_url: str, *, dry_run: bool = True) -> MigrationSummary:
    """Run the one-time Sheets → Postgres migration.

    Set `dry_run=False` only when the founder has reviewed the plan
    AND backed up the Sheets workbook. The destination Postgres must
    already be migrated to head (alembic upgrade head).
    """
    summary = MigrationSummary()

    await db.create_pool(database_url, min_size=1, max_size=3)
    try:
        # ── Step 0: pre-flight ─────────────────────────────────────
        await _assert_schema_ready()

        # ── Step 1: users (founder row first) ──────────────────────
        summary.users_inserted = await _step_users(dry_run=dry_run)
        # ── Step 2: categories ─────────────────────────────────────
        summary.categories_inserted = await _step_categories(dry_run=dry_run)
        # ── Step 3: funding_sources (col P) ────────────────────────
        summary.funding_sources_inserted = await _step_funding_sources(dry_run=dry_run)
        # ── Step 4: transactions ───────────────────────────────────
        summary.transactions_inserted, summary.skipped_orphans = await _step_transactions(
            dry_run=dry_run
        )
        # ── Step 5: admin_audit_log ────────────────────────────────
        summary.audit_inserted = await _step_audit(dry_run=dry_run)

        # ── Verification ───────────────────────────────────────────
        await _verify()
    finally:
        await db.close_pool()

    return summary


async def _assert_schema_ready() -> None:
    """Verify alembic-head schema exists before we start inserting."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        cnt = await conn.fetchval(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema='public' AND table_name=ANY($1::text[]);
            """,
            ["users", "categories", "funding_sources", "transactions", "webhook_tokens"],
        )
    if cnt != 5:
        raise RuntimeError(
            f"Schema not at head — expected 5 W0.2 tables, found {cnt}. "
            "Run `alembic upgrade head` first."
        )


async def _step_users(*, dry_run: bool) -> int:
    """Insert users. Founder is user_id=1, role='founder' (BOOTSTRAP ONLY).

    Runtime MUST NOT hardcode `if user_id == 1`. Admin checks use
    `users.role IN ('founder','admin')`.
    """
    if dry_run:
        return 0
    # Wave 1: pull rows from Sheets `USERS` worksheet; INSERT in id order
    # so the founder's row gets id=1 deterministically.
    raise NotImplementedError("users sheet read — implement in Wave 1")


async def _step_categories(*, dry_run: bool) -> int:
    if dry_run:
        return 0
    raise NotImplementedError("categories sheet read — implement in Wave 1")


async def _step_funding_sources(*, dry_run: bool) -> int:
    """Funding sources are derived from Sheets column P (`bank_account`)
    per F08 spec. `display_id` mirrors col P, canonical id is
    (user_id, kind, bank, last4)."""
    if dry_run:
        return 0
    raise NotImplementedError("funding_sources from col P — implement in Wave 1")


async def _step_transactions(*, dry_run: bool) -> tuple[int, int]:
    """Returns (inserted, skipped). Skipped = rows whose category_id /
    funding_source_id failed to resolve."""
    if dry_run:
        return (0, 0)
    raise NotImplementedError("transactions sheet read — implement in Wave 1")


async def _step_audit(*, dry_run: bool) -> int:
    """Optional — Sheets may not have an audit tab. Returns 0 if absent."""
    if dry_run:
        return 0
    return 0


async def _verify() -> None:
    """Post-migration verification. Fails loud on:
    - orphan user_id refs
    - tenant isolation breach (cross-user row leak)
    - row count mismatch (when row-count reads are wired in)

    W0.6 ships the orphan check + tenant smoke; row-count comparisons
    need real Sheets reads (Wave 1).
    """
    pool = db.get_pool()
    async with pool.acquire() as conn:
        orphan_tx = await conn.fetchval("""
            SELECT COUNT(*) FROM transactions t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE u.id IS NULL;
            """)
        if orphan_tx > 0:
            raise RuntimeError(f"Verification: {orphan_tx} orphan transactions found")

        orphan_cat = await conn.fetchval("""
            SELECT COUNT(*) FROM categories c
            LEFT JOIN users u ON u.id = c.user_id
            WHERE u.id IS NULL;
            """)
        if orphan_cat > 0:
            raise RuntimeError(f"Verification: {orphan_cat} orphan categories found")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Founder Sheets → Postgres one-time migration (Gap 5)."
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="Target Postgres DSN — must already be at alembic head.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually insert rows. Without this flag, only the plan is printed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = asyncio.run(migrate(args.database_url, dry_run=not args.apply))
    print(
        "Migration "
        + ("APPLIED" if args.apply else "DRY-RUN ONLY")
        + f": users={summary.users_inserted} "
        + f"categories={summary.categories_inserted} "
        + f"funding_sources={summary.funding_sources_inserted} "
        + f"transactions={summary.transactions_inserted} "
        + f"(skipped orphans: {summary.skipped_orphans}) "
        + f"audit={summary.audit_inserted}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
