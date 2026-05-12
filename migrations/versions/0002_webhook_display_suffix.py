"""Add `display_suffix` column to `webhook_tokens`.

Gap 3 follow-up — supports F07 UI display rule (W0.8).

Strictly additive: nullable VARCHAR(8) column on `webhook_tokens`. No
backfill of historical rows — founder accepts that pre-migration tokens
render in F07 settings UI without a suffix (Auth path is unaffected;
`resolve_token` still goes through `token_hash`).

VARCHAR(8) (not CHAR(6)) for future-proofing: only 6 chars used today
(`raw_token[-6:]`), but column tolerates 7–8 if a future kind ever
wants a longer tail.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE webhook_tokens ADD COLUMN display_suffix VARCHAR(8);")


def downgrade() -> None:
    op.execute("ALTER TABLE webhook_tokens DROP COLUMN display_suffix;")
