"""B-1: Multi-source dashboard parsers — roadmap §1/§2/§6/§7 + doc versions.

Tests are pure-read: parser must NOT mutate roadmap or any source file.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from scripts.dashboard.build_json import build_dashboard_json
from scripts.dashboard.parse_docs import compute_staleness, parse_doc_version_header
from scripts.dashboard.parse_roadmap import (
    parse_roadmap_blockers,
    parse_roadmap_features,
    parse_roadmap_overall_progress,
    parse_roadmap_risks,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_roadmap_section_1_overall_progress() -> None:
    result = parse_roadmap_overall_progress(_read("roadmap_section_1.md"))
    assert "overall_progress" in result
    assert isinstance(result["overall_progress"], int)
    assert 0 <= result["overall_progress"] <= 100
    assert "phases" in result
    assert isinstance(result["phases"], list)
    assert len(result["phases"]) >= 6
    p0 = result["phases"][0]
    assert "name" in p0
    assert "status" in p0
    assert "progress" in p0


def test_parse_roadmap_section_2_features() -> None:
    features = parse_roadmap_features(_read("roadmap_section_2.md"))
    assert isinstance(features, list)
    assert len(features) >= 10
    f01 = next((f for f in features if f["id"] == "F01"), None)
    assert f01 is not None
    for key in ("id", "name", "spec", "be_tech", "be_code", "bot_code", "phase"):
        assert key in f01
    # F01 spec = ✅ done, bot_code = ⬜ not_started in fixture
    assert f01["spec"] == "done"
    assert f01["bot_code"] == "not_started"


def test_parse_roadmap_section_6_blockers() -> None:
    blockers = parse_roadmap_blockers(_read("roadmap_section_6.md"))
    assert isinstance(blockers, list)
    assert len(blockers) >= 4
    b0 = blockers[0]
    for key in ("name", "affects", "status", "notes"):
        assert key in b0


def test_parse_roadmap_section_7_risks() -> None:
    risks = parse_roadmap_risks(_read("roadmap_section_7.md"))
    assert isinstance(risks, list)
    assert len(risks) >= 4
    r0 = risks[0]
    for key in ("name", "phase", "impact", "mitigation"):
        assert key in r0
    impacts = {r["impact"] for r in risks}
    assert impacts & {"Low", "Medium", "High"}


def test_parse_doc_version_header(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(
        "# Sample\n\n"
        "> **Version:** v3.1.0\n"
        "> **Ngày tạo:** 2026-05-05\n"
        "> **Cập nhật lần cuối:** 2026-05-10\n"
        "> **Trạng thái:** Draft\n",
        encoding="utf-8",
    )
    out = parse_doc_version_header(doc)
    assert out["name"] == "sample.md"
    assert out["version"] == "v3.1.0"
    assert out["updated"] == "2026-05-10"
    assert isinstance(out["stale_days"], int)


def test_doc_staleness_yellow_at_8_days() -> None:
    today = date(2026, 5, 18)
    days = compute_staleness("2026-05-10", today)
    assert days == 8
    # Phase 5 will assert color class >=7 → yellow.


def test_doc_staleness_red_at_15_days() -> None:
    today = date(2026, 5, 25)
    days = compute_staleness("2026-05-10", today)
    assert days == 15


def test_build_dashboard_json_schema_complete() -> None:
    tracker: dict[str, Any] = {"mvp": {"merged": 6, "total": 35, "percent": 17}, "phases": []}
    roadmap: dict[str, Any] = {
        "overall": {"overall_progress": 30, "phases": []},
        "features": [],
        "blockers": [],
        "risks": [],
    }
    docs: list[dict[str, Any]] = []
    out = build_dashboard_json(tracker, roadmap, docs)
    for key in ("generated_at", "overall", "phases", "features", "blockers", "risks", "docs"):
        assert key in out, f"missing key: {key}"


def test_no_roadmap_mutation() -> None:
    """Parsers must NOT mutate source text."""
    text = _read("roadmap_section_2.md")
    original = text
    parse_roadmap_features(text)
    assert text == original


@pytest.mark.parametrize(
    "emoji,expected",
    [("✅", "done"), ("🟡", "partial"), ("⬜", "not_started"), ("❌", "blocked")],
)
def test_status_emoji_mapping(emoji: str, expected: str) -> None:
    from scripts.dashboard.parse_roadmap import _status_from_emoji

    assert _status_from_emoji(emoji) == expected
