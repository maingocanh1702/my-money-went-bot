"""Migration smoke tests.

Verifies:
  - `alembic upgrade head` creates all 11 tables
  - `alembic downgrade base` drops them all cleanly
  - funding_sources + transactions.funding_source_id FK exists (Gap 1)
  - webhook_tokens with hashed token + kind check exists (Gap 3)
  - INSERT/SELECT smoke roundtrip on users + transactions
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

EXPECTED_TABLES = {
    "users",
    "bank_connections",
    "categories",
    "funding_sources",
    "transactions",
    "webhook_tokens",
    "bot_state",
    "scheduled_jobs",
    "monthly_reports",
    "admin_audit_log",
    "analytics_events",
}


def _list_public_tables(conn: psycopg.Connection) -> set[str]:
    cur = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
    return {row[0] for row in cur.fetchall()}


def test_upgrade_creates_all_tables(migrated_db: str) -> None:
    """After `alembic upgrade head`, all 11 expected tables exist."""
    with psycopg.connect(migrated_db) as conn:
        tables = _list_public_tables(conn)
    # alembic_version is metadata; ignore.
    tables.discard("alembic_version")
    assert (
        tables == EXPECTED_TABLES
    ), f"Missing: {EXPECTED_TABLES - tables}; Extra: {tables - EXPECTED_TABLES}"


def test_funding_source_fk_on_transactions(migrated_db: str) -> None:
    """Gap 1: transactions.funding_source_id FK exists, nullable, SET NULL on delete."""
    with psycopg.connect(migrated_db) as conn:
        cur = conn.execute(
            """
            SELECT a.attname, a.attnotnull, c.confdeltype
            FROM pg_attribute a
            LEFT JOIN pg_constraint c
              ON c.conrelid = a.attrelid AND a.attnum = ANY(c.conkey) AND c.contype = 'f'
            WHERE a.attrelid = 'transactions'::regclass
              AND a.attname = 'funding_source_id';
            """
        )
        row = cur.fetchone()
    assert row is not None, "transactions.funding_source_id column missing"
    name, notnull, deltype = row
    assert name == "funding_source_id"
    assert notnull is False, "funding_source_id must be NULLABLE per Gap 1"
    assert deltype == "n", f"ON DELETE action must be SET NULL ('n'), got {deltype!r}"


def test_webhook_tokens_shape(migrated_db: str) -> None:
    """Gap 3: webhook_tokens has token_hash UNIQUE + kind check constraint."""
    with psycopg.connect(migrated_db) as conn:
        cur = conn.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'webhook_tokens'
            ORDER BY ordinal_position;
            """
        )
        cols = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

        cur = conn.execute(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'webhook_tokens'::regclass
              AND contype = 'c';
            """
        )
        checks = [row[0] for row in cur.fetchall()]

    assert "token_hash" in cols, "webhook_tokens.token_hash missing"
    assert "kind" in cols
    assert "user_id" in cols
    assert "revoked_at" in cols
    # Kind check should restrict to sepay/email_inbound
    assert any(
        "sepay" in c and "email_inbound" in c for c in checks
    ), f"kind CHECK constraint missing or wrong: {checks}"


def test_users_channel_type_accepts_zalo(migrated_db: str) -> None:
    """Zalo is a first-class channel_type in the users CHECK constraint."""
    with psycopg.connect(migrated_db, autocommit=True) as conn:
        conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")
        try:
            conn.execute(
                """
                INSERT INTO users (channel_type, channel_user_id, display_name)
                VALUES ('zalo', 'zalo-user-1', 'Zalo User');
                """
            )
            cur = conn.execute(
                "SELECT channel_type FROM users WHERE channel_user_id = 'zalo-user-1';"
            )
            assert cur.fetchone() == ("zalo",)
        finally:
            conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")


def test_users_channel_chat_id_column_exists_and_accepts_long_string(
    migrated_db: str,
) -> None:
    """Zalo routing IDs are string IDs and may exceed BIGINT range."""
    long_channel_chat_id = "123456789012345678901234567890"
    with psycopg.connect(migrated_db, autocommit=True) as conn:
        conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")
        try:
            conn.execute(
                """
                INSERT INTO users (
                    channel_type, channel_user_id, channel_chat_id, display_name
                )
                VALUES ('zalo', 'zalo-user-long-chat', %s, 'Zalo Long Chat');
                """,
                (long_channel_chat_id,),
            )
            cur = conn.execute(
                """
                SELECT channel_chat_id
                FROM users
                WHERE channel_user_id = 'zalo-user-long-chat';
                """
            )
            assert cur.fetchone() == (long_channel_chat_id,)
        finally:
            conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")


def test_users_channel_chat_id_index_exists(migrated_db: str) -> None:
    """Zalo routing lookups get a partial index for populated chat IDs."""
    with psycopg.connect(migrated_db) as conn:
        cur = conn.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'users'
              AND indexname = 'idx_users_channel_chat_id';
            """
        )
        row = cur.fetchone()
    assert row is not None, "idx_users_channel_chat_id missing"
    indexdef = row[0]
    assert "channel_chat_id" in indexdef
    assert "WHERE (channel_chat_id IS NOT NULL)" in indexdef


def test_downgrade_drops_all_tables(pg_url: str) -> None:
    """`alembic downgrade base` drops every table including alembic_version data."""
    env = os.environ.copy()
    env["DATABASE_URL"] = pg_url

    # Ensure upgraded first (migrated_db session fixture may not have run).
    up = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert up.returncode == 0, up.stderr

    down = subprocess.run(
        ["alembic", "downgrade", "base"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert down.returncode == 0, down.stderr

    with psycopg.connect(pg_url) as conn:
        tables = _list_public_tables(conn)
    tables.discard("alembic_version")
    assert tables == set(), f"Tables left after downgrade: {tables}"

    # Re-upgrade for downstream tests in this session.
    re_up = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert re_up.returncode == 0, re_up.stderr


def test_insert_select_smoke(migrated_db: str) -> None:
    """Basic INSERT/SELECT roundtrip — users + transactions."""
    with psycopg.connect(migrated_db, autocommit=True) as conn:
        # Cleanup any prior data in this session
        conn.execute("TRUNCATE users RESTART IDENTITY CASCADE;")
        conn.execute(
            """
            INSERT INTO users (channel_type, channel_user_id, display_name)
            VALUES ('telegram', '999', 'Smoke User') RETURNING id;
            """
        )
        cur = conn.execute("SELECT id, plan, role FROM users WHERE channel_user_id='999';")
        row = cur.fetchone()
        assert row is not None
        user_id, plan, role = row
        assert plan == "free"
        assert role == "user"

        conn.execute(
            """
            INSERT INTO transactions
                (user_id, tx_date, direction, amount, source, month_key)
            VALUES (%s, NOW(), 'out', 50000, 'sepay', '2026-05');
            """,
            (user_id,),
        )
        cur = conn.execute("SELECT amount FROM transactions WHERE user_id=%s;", (user_id,))
        assert cur.fetchone() == (50000,)


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_each_table_queryable(migrated_db: str, table: str) -> None:
    """Each table accepts a trivial SELECT (catches typos in DDL)."""
    from psycopg import sql

    with psycopg.connect(migrated_db) as conn:
        query = sql.SQL("SELECT COUNT(*) FROM {tbl}").format(tbl=sql.Identifier(table))
        cur = conn.execute(query)
        row = cur.fetchone()
        assert row is not None
