"""F01 — pure-function unit tests for user_svc.

DB-free coverage of the small, deterministic helpers around /start:
  - generate_inbound_email format (matches migration 0003 backfill)
  - compute_trial_end default 14 days
  - current_month_key format
  - DEFAULT_CATEGORIES seed shape (slugs + caps)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def test_generate_inbound_email_format() -> None:
    from core.services.user_svc import generate_inbound_email

    assert generate_inbound_email(42) == "u42@in.mymoneywent.com"
    assert generate_inbound_email(1) == "u1@in.mymoneywent.com"


def test_compute_trial_end_default_14d() -> None:
    from core.services.user_svc import compute_trial_end

    fixed = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
    assert compute_trial_end(now=fixed) == fixed + timedelta(days=14)


def test_compute_trial_end_custom_days() -> None:
    from core.services.user_svc import compute_trial_end

    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    assert compute_trial_end(days=7, now=fixed) == fixed + timedelta(days=7)


def test_current_month_key_format() -> None:
    from core.services.user_svc import current_month_key

    fixed = datetime(2026, 5, 13, tzinfo=UTC)
    assert current_month_key(now=fixed) == "2026-05"


def test_default_categories_seed_shape() -> None:
    from core.services.user_svc import DEFAULT_CATEGORIES

    slugs = [c["slug"] for c in DEFAULT_CATEGORIES]
    assert slugs == ["daily_spending", "saving", "subscription"]
    caps = {c["slug"]: c["daily_cap"] for c in DEFAULT_CATEGORIES}
    assert caps["daily_spending"] == 100_000
    assert caps["saving"] is None
    assert caps["subscription"] is None
    # i18n keys present.
    for cat in DEFAULT_CATEGORIES:
        assert "i18n_key" in cat
        assert str(cat["i18n_key"]).startswith("cat.default.")
