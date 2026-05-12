"""Unit tests for spec_lint.

Tests use a tmp_path with synthetic specs to avoid coupling to real
docs/features/ content (which evolves independently).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.autopilot.config import Config
from tools.autopilot.spec_lint import lint


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "features" / "BE").mkdir(parents=True)
    (tmp_path / ".autopilot" / "state").mkdir(parents=True)
    return tmp_path


def _make_cfg(repo: Path) -> Config:
    base = Config(
        repo_root=repo,
        codex_bin="codex",
        claude_bin="claude",
        state_dir=repo / ".autopilot" / "state",
    )
    return base


GOOD_FE = """\
# Feature: Test — Sample (F99)

> **Version:** v1.0.0

## 1. Mô tả

Sample.

## 2. Use Cases + Edge Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | User | Click | Done |

## 10. Acceptance Criteria

- [ ] Criterion one is testable.
- [ ] Criterion two is testable.
- [ ] Criterion three is testable.

<!-- autopilot:meta
feature_id: F99
branch: feat/F99-sample
-->

<!-- autopilot:gaps
- id: G1
  question: stub
  status: CLOSED
  decision: foo
-->

<!-- autopilot:test_plan
happy_path:
  - test_basic: returns expected
retry_idempotency:
  - N/A — pure read
missing_optional_fields:
  - test_null: returns default
pathological_inputs:
  - test_huge: rejects gracefully
concurrent_access:
  - N/A — single-user
-->

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | init |
"""

GOOD_BE = """\
# BE Tech Doc: Test (F99)

## 1. Implementation Overview

Sample.

## 5. Testing Plan

| Test | Layer | Categories |
|------|-------|------------|
| test_a | unit | happy |

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | init |
"""


def test_good_spec_passes(fake_repo: Path) -> None:
    (fake_repo / "docs/features/feature-test.md").write_text(GOOD_FE)
    (fake_repo / "docs/features/BE/feature-test-tech.md").write_text(GOOD_BE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "F99")
    assert report.ok, report.render()


def test_missing_be_doc_fails(fake_repo: Path) -> None:
    (fake_repo / "docs/features/feature-test.md").write_text(GOOD_FE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "F99")
    assert not report.ok
    assert any("BE tech doc not found" in e for e in report.errors)


def test_missing_acceptance_section_fails(fake_repo: Path) -> None:
    bad_fe = GOOD_FE.replace("## 10. Acceptance Criteria", "## 10. Other Stuff")
    (fake_repo / "docs/features/feature-test.md").write_text(bad_fe)
    (fake_repo / "docs/features/BE/feature-test-tech.md").write_text(GOOD_BE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "F99")
    assert not report.ok
    assert any("Acceptance Criteria" in e for e in report.errors)


def test_open_gap_fails(fake_repo: Path) -> None:
    bad_fe = GOOD_FE.replace("status: CLOSED", "status: OPEN")
    (fake_repo / "docs/features/feature-test.md").write_text(bad_fe)
    (fake_repo / "docs/features/BE/feature-test-tech.md").write_text(GOOD_BE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "F99")
    assert not report.ok
    assert any("OPEN gap" in e for e in report.errors)


def test_todo_in_acceptance_fails(fake_repo: Path) -> None:
    bad_fe = GOOD_FE.replace(
        "Criterion three is testable.",
        "Criterion three TBD",
    )
    (fake_repo / "docs/features/feature-test.md").write_text(bad_fe)
    (fake_repo / "docs/features/BE/feature-test-tech.md").write_text(GOOD_BE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "F99")
    assert not report.ok
    assert any("open marker" in e for e in report.errors)


def test_too_few_acceptance_items_fails(fake_repo: Path) -> None:
    bad_fe = GOOD_FE.replace(
        "- [ ] Criterion two is testable.\n- [ ] Criterion three is testable.\n",
        "",
    )
    (fake_repo / "docs/features/feature-test.md").write_text(bad_fe)
    (fake_repo / "docs/features/BE/feature-test-tech.md").write_text(GOOD_BE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "F99")
    assert not report.ok
    assert any(">=3" in e for e in report.errors)


def test_missing_test_plan_category_fails(fake_repo: Path) -> None:
    bad_fe = GOOD_FE.replace(
        "concurrent_access:\n  - N/A — single-user\n",
        "",
    )
    (fake_repo / "docs/features/feature-test.md").write_text(bad_fe)
    (fake_repo / "docs/features/BE/feature-test-tech.md").write_text(GOOD_BE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "F99")
    assert not report.ok
    assert any("concurrent_access" in e for e in report.errors)


def test_no_meta_block_warns_only(fake_repo: Path) -> None:
    # Resolve via filename (not meta block). Use feature_id matching the stem.
    bad_fe = GOOD_FE.replace(
        "<!-- autopilot:meta\nfeature_id: F99\nbranch: feat/F99-sample\n-->\n",
        "",
    )
    (fake_repo / "docs/features/feature-test.md").write_text(bad_fe)
    (fake_repo / "docs/features/BE/feature-test-tech.md").write_text(GOOD_BE)
    cfg = _make_cfg(fake_repo)
    report = lint(cfg, "test")
    assert report.ok, report.render()  # meta block is optional
    assert any("autopilot:meta" in w for w in report.warnings)
