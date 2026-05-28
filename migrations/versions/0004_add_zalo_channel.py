"""Add Zalo channel routing support to users.

Adds `zalo` to the users channel_type CHECK constraint and stores optional
string channel routing IDs in `users.channel_chat_id`. This preserves the
existing Telegram `chat_id BIGINT` contract while allowing Zalo IDs that may
exceed BIGINT range.

Downgrade safety: downgrade restores the old channel_type CHECK constraint
without `zalo`, so it is only valid after all `users.channel_type = 'zalo'`
rows have been removed or migrated away.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-28 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT chk_channel_type;")
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT chk_channel_type
        CHECK (channel_type IN ('telegram', 'messenger', 'discord', 'zalo'));
        """
    )
    op.execute("ALTER TABLE users ADD COLUMN channel_chat_id TEXT;")
    op.execute(
        """
        CREATE INDEX idx_users_channel_chat_id
        ON users(channel_chat_id)
        WHERE channel_chat_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX idx_users_channel_chat_id;")
    op.execute("ALTER TABLE users DROP COLUMN channel_chat_id;")
    op.execute("ALTER TABLE users DROP CONSTRAINT chk_channel_type;")
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT chk_channel_type
        CHECK (channel_type IN ('telegram', 'messenger', 'discord'));
        """
    )
