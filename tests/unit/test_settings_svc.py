"""Unit tests for core.settings_svc — pure functions only (no DB).

Covers the slices of the F07 test plan that don't touch a connection:
  - happy_path subset: compute_plan_status branches (G5)
  - pathological_inputs: is_valid_timezone hardening

DB-touching tests live in tests/integration/test_settings_*.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.settings_svc import compute_plan_status, is_valid_timezone

# ── Happy path (pure) ────────────────────────────────────────────────


def test_compute_plan_status_free_ignores_trial_columns() -> None:
    """Free plan always renders 'free' even if trial/expiry columns are set."""
    now = datetime(2026, 5, 12, tzinfo=UTC)
    info = compute_plan_status(
        "free",
        trial_ends_at=now + timedelta(days=10),
        plan_expires_at=now + timedelta(days=30),
        now=now,
    )
    assert info.status == "free"
    assert info.days_left is None


def test_compute_plan_status_trial_days_rounded_up() -> None:
    """5d + 1h remaining → 'trial, 6 days left' (round up partial day)."""
    now = datetime(2026, 5, 12, tzinfo=UTC)
    info = compute_plan_status(
        "pro",
        trial_ends_at=now + timedelta(days=5, hours=1),
        plan_expires_at=None,
        now=now,
    )
    assert info.status == "trial"
    assert info.days_left == 6


def test_compute_plan_status_trial_under_24h_rounds_to_one() -> None:
    """<24h left must not render as 0 days — round to 1."""
    now = datetime(2026, 5, 12, tzinfo=UTC)
    info = compute_plan_status(
        "business",
        trial_ends_at=now + timedelta(hours=2),
        plan_expires_at=None,
        now=now,
    )
    assert info.status == "trial"
    assert info.days_left == 1


def test_compute_plan_status_expired_when_past_expiry() -> None:
    now = datetime(2026, 5, 12, tzinfo=UTC)
    info = compute_plan_status(
        "pro",
        trial_ends_at=None,
        plan_expires_at=now - timedelta(days=1),
        now=now,
    )
    assert info.status == "expired"


def test_compute_plan_status_active_pro() -> None:
    now = datetime(2026, 5, 12, tzinfo=UTC)
    info = compute_plan_status(
        "pro",
        trial_ends_at=None,
        plan_expires_at=now + timedelta(days=30),
        now=now,
    )
    assert info.status == "active"
    assert info.days_left is None


def test_compute_plan_status_trial_takes_precedence_over_expiry() -> None:
    """An active trial trumps a (theoretically expired) plan_expires_at."""
    now = datetime(2026, 5, 12, tzinfo=UTC)
    info = compute_plan_status(
        "pro",
        trial_ends_at=now + timedelta(days=2),
        plan_expires_at=now - timedelta(days=10),
        now=now,
    )
    assert info.status == "trial"
    assert info.days_left == 2


# ── Pathological — is_valid_timezone (no DB) ─────────────────────────


def test_valid_timezone_accepts_known_iana() -> None:
    assert is_valid_timezone("Asia/Ho_Chi_Minh")
    assert is_valid_timezone("Asia/Tokyo")
    assert is_valid_timezone("UTC")
    assert is_valid_timezone("Europe/London")


def test_valid_timezone_rejects_unknown() -> None:
    assert not is_valid_timezone("ABC")
    assert not is_valid_timezone("Atlantis/Lost_City")


def test_valid_timezone_rejects_empty_string() -> None:
    assert not is_valid_timezone("")


def test_valid_timezone_rejects_sql_injection_shaped_input() -> None:
    """Membership check kicks SQLi-shaped strings out before any DB call."""
    assert not is_valid_timezone("Asia/Ho_Chi_Minh'; DROP TABLE users; --")
    assert not is_valid_timezone("' OR 1=1 --")


def test_valid_timezone_rejects_extremely_long_input() -> None:
    """10KB string fails the length gate, never reaches zoneinfo lookup."""
    payload = "A" * 10_000
    assert not is_valid_timezone(payload)


def test_valid_timezone_rejects_at_boundary_above_64_chars() -> None:
    """users.timezone is VARCHAR(64); reject anything that wouldn't fit."""
    payload = "a" * 65
    assert not is_valid_timezone(payload)
