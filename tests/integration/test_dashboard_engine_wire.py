"""Integration e2e — build-dashboard.py invokes engine + projection end-to-end.

Phase A wire-up: tracker → engine → projection → dashboard.{html,md,json}.
Uses --no-network mode for deterministic test environment.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bd() -> Any:
    """Load build-dashboard.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "build_dashboard_wire", ROOT / "scripts" / "build-dashboard.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_dashboard_wire"] = module
    spec.loader.exec_module(module)
    return module


def test_full_pipeline_tracker_to_html_with_state_block(bd: Any, tmp_path: pathlib.Path) -> None:
    """Full pipeline: tracker → engine → projection → HTML with state block."""
    tracker = ROOT / "docs" / "implementation-tracker.md"
    if not tracker.exists():
        pytest.skip("tracker not found")

    dashboard_dir = tmp_path / ".dashboard"
    html_out = tmp_path / "dashboard.html"
    md_out = tmp_path / "dashboard.md"
    json_out = tmp_path / "dashboard.json"

    bd.main(
        argv=[
            "--no-network",
            "--dashboard-dir",
            str(dashboard_dir),
            "--output-html",
            str(html_out),
            "--output-md",
            str(md_out),
            "--output-json",
            str(json_out),
        ]
    )

    assert html_out.exists()
    assert md_out.exists()
    assert json_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert "features" in data


def _strip_timestamps(text: str) -> str:
    """Remove volatile timestamps for idempotency comparison."""
    import re

    text = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\+\d{2}:\d{2}|Z)?", "TS", text)
    return text


def test_idempotent_full_pipeline(bd: Any, tmp_path: pathlib.Path) -> None:
    """Run build-dashboard twice → outputs structurally identical (modulo timestamps)."""
    tracker = ROOT / "docs" / "implementation-tracker.md"
    if not tracker.exists():
        pytest.skip("tracker not found")

    dashboard_dir = tmp_path / ".dashboard"
    html_out = tmp_path / "dashboard.html"
    md_out = tmp_path / "dashboard.md"
    json_out = tmp_path / "dashboard.json"

    argv = [
        "--no-network",
        "--dashboard-dir",
        str(dashboard_dir),
        "--output-html",
        str(html_out),
        "--output-md",
        str(md_out),
        "--output-json",
        str(json_out),
    ]

    bd.main(argv=argv)
    html_1 = _strip_timestamps(html_out.read_text(encoding="utf-8"))
    json_1 = _strip_timestamps(json_out.read_text(encoding="utf-8"))

    bd.main(argv=argv)
    html_2 = _strip_timestamps(html_out.read_text(encoding="utf-8"))
    json_2 = _strip_timestamps(json_out.read_text(encoding="utf-8"))

    assert html_1 == html_2
    assert json_1 == json_2
