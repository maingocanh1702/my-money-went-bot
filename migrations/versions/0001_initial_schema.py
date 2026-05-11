"""Initial schema — 11 tables.

Source of truth: docs/tdd-vi.md §2.1 (DDL).

Tables created (in dependency order):
  1.  users
  2.  bank_connections
  3.  categories
  4.  funding_sources                (F08 / Gap 1)
  5.  transactions                   (with funding_source_id FK)
  6.  webhook_tokens                 (Gap 3 — dedicated, hashed)
  7.  bot_state
  8.  scheduled_jobs
  9.  monthly_reports
  10. admin_audit_log
  11. analytics_events

Gap decisions applied:
  - Gap 1: funding_sources table shell + transactions.funding_source_id
           INTEGER NULL REFERENCES funding_sources(id) ON DELETE SET NULL.
  - Gap 3: webhook_tokens dedicated table, token_hash TEXT (SHA256 hex).
           users.webhook_token column NOT included — moved into this
           dedicated table.

Raw DDL via op.execute keeps schema readable and 1:1 with TDD spec.

Revision ID: 0001
Revises:
Create Date: 2026-05-11 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. users ────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE users (
            id                   SERIAL PRIMARY KEY,
            channel_type         VARCHAR(16)  NOT NULL,
            channel_user_id      VARCHAR(64)  NOT NULL,
            chat_id              BIGINT,
            last_user_message_at TIMESTAMPTZ,
            telegram_id          BIGINT,
            username             VARCHAR(64),
            display_name         VARCHAR(128),
            inbound_email        VARCHAR(64)  UNIQUE,
            plan                 VARCHAR(16)  NOT NULL DEFAULT 'free',
            trial_ends_at        TIMESTAMPTZ,
            plan_expires_at      TIMESTAMPTZ,
            timezone             VARCHAR(64)  NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
            locale               VARCHAR(5)   NOT NULL DEFAULT 'vi',
            daily_recap_enabled  BOOLEAN      NOT NULL DEFAULT TRUE,
            onboard_path         VARCHAR(8),
            invalid_channel      BOOLEAN      NOT NULL DEFAULT FALSE,
            bot_id               INTEGER,
            role                 VARCHAR(16)  NOT NULL DEFAULT 'user',
            created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_plan         CHECK (plan IN ('free', 'pro', 'business')),
            CONSTRAINT chk_channel_type CHECK (channel_type IN ('telegram', 'messenger', 'discord')),
            CONSTRAINT chk_locale       CHECK (locale IN ('vi', 'en')),
            CONSTRAINT chk_role         CHECK (role IN ('user', 'founder', 'admin')),
            CONSTRAINT uniq_channel_user UNIQUE (channel_type, channel_user_id)
        );
        """
    )
    op.execute("CREATE INDEX idx_users_channel ON users(channel_type, channel_user_id);")
    op.execute(
        "CREATE INDEX idx_users_telegram_legacy ON users(telegram_id) "
        "WHERE telegram_id IS NOT NULL;"
    )

    # ── 2. bank_connections ────────────────────────────────────
    op.execute(
        """
        CREATE TABLE bank_connections (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type        VARCHAR(16) NOT NULL,
            bank_name   VARCHAR(32),
            label       VARCHAR(64),
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_conn_type CHECK (type IN ('sepay', 'email'))
        );
        """
    )
    op.execute("CREATE INDEX idx_bank_conn_user ON bank_connections(user_id);")

    # ── 3. categories ──────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE categories (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            slug        VARCHAR(64) NOT NULL,
            name        VARCHAR(128) NOT NULL,
            allocated   BIGINT NOT NULL DEFAULT 0,
            daily_cap   BIGINT,
            month_key   VARCHAR(7) NOT NULL,
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, slug, month_key)
        );
        """
    )
    op.execute("CREATE INDEX idx_cat_user_month ON categories(user_id, month_key);")

    # ── 4. funding_sources (Gap 1) ─────────────────────────────
    op.execute(
        """
        CREATE TABLE funding_sources (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind            VARCHAR(16) NOT NULL,
            bank            VARCHAR(16) NOT NULL,
            last4           VARCHAR(4)  NOT NULL DEFAULT '',
            display_id      VARCHAR(32) NOT NULL,
            nickname        VARCHAR(32),
            first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_tx_at      TIMESTAMPTZ,
            status          VARCHAR(16) NOT NULL DEFAULT 'active',
            archived_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, kind, bank, last4),
            CONSTRAINT chk_fs_kind   CHECK (kind IN
                ('bank_account','debit_card','credit_card','e_wallet')),
            CONSTRAINT chk_fs_status CHECK (status IN ('active','hidden','archived')),
            CONSTRAINT chk_fs_archived_consistency CHECK (
                (status = 'archived' AND archived_at IS NOT NULL)
                OR (status <> 'archived' AND archived_at IS NULL)
            )
        );
        """
    )
    op.execute("CREATE INDEX idx_fs_user_status  ON funding_sources(user_id, status);")
    op.execute("CREATE INDEX idx_fs_user_lasttx  ON funding_sources(user_id, last_tx_at DESC);")
    op.execute("CREATE INDEX idx_fs_user_display ON funding_sources(user_id, display_id);")

    # ── 5. transactions (with funding_source_id FK) ────────────
    op.execute(
        """
        CREATE TABLE transactions (
            id                SERIAL PRIMARY KEY,
            user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tx_date           TIMESTAMPTZ NOT NULL,
            description       VARCHAR(512),
            direction         VARCHAR(4)  NOT NULL,
            amount            BIGINT      NOT NULL,
            ref_code          VARCHAR(64),
            source            VARCHAR(32) NOT NULL DEFAULT 'sepay',
            category_id       INTEGER REFERENCES categories(id),
            funding_source_id INTEGER REFERENCES funding_sources(id) ON DELETE SET NULL,
            confirmed         BOOLEAN     NOT NULL DEFAULT FALSE,
            month_key         VARCHAR(7)  NOT NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, ref_code),
            CONSTRAINT chk_direction CHECK (direction IN ('in', 'out'))
        );
        """
    )
    op.execute("CREATE INDEX idx_tx_user_month ON transactions(user_id, month_key);")
    op.execute("CREATE INDEX idx_tx_user_date  ON transactions(user_id, tx_date);")
    op.execute("CREATE INDEX idx_tx_user_fs    ON transactions(user_id, funding_source_id);")

    # ── 6. webhook_tokens (Gap 3) ──────────────────────────────
    op.execute(
        """
        CREATE TABLE webhook_tokens (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind        TEXT NOT NULL,
            token_hash  TEXT NOT NULL UNIQUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at  TIMESTAMPTZ,
            CONSTRAINT chk_webhook_token_kind CHECK (kind IN ('sepay', 'email_inbound')),
            UNIQUE(user_id, kind)
        );
        """
    )
    op.execute("CREATE INDEX idx_webhook_tokens_user ON webhook_tokens(user_id);")

    # ── 7. bot_state ───────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE bot_state (
            user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            step        VARCHAR(48),
            payload     JSONB NOT NULL DEFAULT '{}',
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX idx_bot_state_step ON bot_state(step) WHERE step IS NOT NULL;")

    # ── 8. scheduled_jobs ──────────────────────────────────────
    op.execute(
        """
        CREATE TABLE scheduled_jobs (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_type     VARCHAR(32) NOT NULL,
            enabled      BOOLEAN NOT NULL DEFAULT TRUE,
            next_run_utc TIMESTAMPTZ,
            last_run_utc TIMESTAMPTZ,
            config       JSONB DEFAULT '{}',
            UNIQUE(user_id, job_type)
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_jobs_next_run ON scheduled_jobs(next_run_utc) WHERE enabled = TRUE;"
    )

    # ── 9. monthly_reports ─────────────────────────────────────
    op.execute(
        """
        CREATE TABLE monthly_reports (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            month_key     VARCHAR(7) NOT NULL,
            category_name VARCHAR(128),
            allocated     BIGINT,
            spent         BIGINT,
            remaining     BIGINT,
            pct           INTEGER,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    # ── 10. admin_audit_log ────────────────────────────────────
    op.execute(
        """
        CREATE TABLE admin_audit_log (
            id                BIGSERIAL PRIMARY KEY,
            admin_telegram_id BIGINT NOT NULL,
            command           VARCHAR(64) NOT NULL,
            target_user_id    INTEGER REFERENCES users(id),
            payload           JSONB,
            result            VARCHAR(16),
            error_message     TEXT,
            executed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_admin_audit_admin "
        "ON admin_audit_log(admin_telegram_id, executed_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_admin_audit_target "
        "ON admin_audit_log(target_user_id, executed_at DESC);"
    )

    # ── 11. analytics_events ───────────────────────────────────
    op.execute(
        """
        CREATE TABLE analytics_events (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER,
            event_name  VARCHAR(64) NOT NULL,
            properties  JSONB DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX idx_analytics_event ON analytics_events(event_name, created_at);")


def downgrade() -> None:
    # Reverse order — FK dependencies.
    op.execute("DROP TABLE IF EXISTS analytics_events;")
    op.execute("DROP TABLE IF EXISTS admin_audit_log;")
    op.execute("DROP TABLE IF EXISTS monthly_reports;")
    op.execute("DROP TABLE IF EXISTS scheduled_jobs;")
    op.execute("DROP TABLE IF EXISTS bot_state;")
    op.execute("DROP TABLE IF EXISTS webhook_tokens;")
    op.execute("DROP TABLE IF EXISTS transactions;")
    op.execute("DROP TABLE IF EXISTS funding_sources;")
    op.execute("DROP TABLE IF EXISTS categories;")
    op.execute("DROP TABLE IF EXISTS bank_connections;")
    op.execute("DROP TABLE IF EXISTS users;")
