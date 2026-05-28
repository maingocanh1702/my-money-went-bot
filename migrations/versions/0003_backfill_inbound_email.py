"""Backfill `users.inbound_email` for legacy NULL rows.

Companion to F07 G4 refactor (2026-05-13): `core.settings_svc.get_overview`
is now PURE READ. The implicit on-read backfill (R2/R3 root cause) is
extracted to `ensure_inbound_email`. This migration handles existing NULL
rows once; new users get the column populated at user-creation time by
F-onboarding/W0.

Idempotent — `WHERE inbound_email IS NULL` makes a second `alembic upgrade
head` a no-op. The formula `u{id}@in.mymoneywent.com` matches
`ensure_inbound_email` / `fallback_inbound_email` so display and persisted
values agree.

UNIQUE constraint on the column already enforces collision safety; the
formula is a deterministic function of `users.id` (itself UNIQUE), so no
collisions are possible.

Downgrade is a no-op: we cannot safely restore the prior NULL state —
some rows may have been NULL pre-migration and others not. Founder accepts
the irreversibility (P2 risk tier; data, not schema).

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-13 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE users
        SET inbound_email = 'u' || id::text || '@in.mymoneywent.com',
            updated_at = NOW()
        WHERE inbound_email IS NULL;
        """)


def downgrade() -> None:
    # No-op: pre-migration NULL/non-NULL state is not recoverable from the
    # post-migration values. See module docstring.
    pass
