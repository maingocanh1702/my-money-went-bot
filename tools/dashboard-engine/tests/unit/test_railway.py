"""Tests for Railway deploy collector per spec §6.7."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "railway"


class TestCollectRailwaySignals:
    def test_deployed_success(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        data = json.loads((FIXTURES / "deploy_success.json").read_text())

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            return_value=data,
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["deploy_state"] == "deployed"
        assert result["last_deploy_at"] == "2026-05-20T12:00:00Z"
        assert "railway_unknown" not in result["warnings"]
        assert result["overlays"] == []

    def test_deploying_building(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        data = json.loads((FIXTURES / "deploy_building.json").read_text())

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            return_value=data,
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["deploy_state"] == "deploying"

    def test_deploy_failed(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        data = json.loads((FIXTURES / "deploy_failed.json").read_text())

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            return_value=data,
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["deploy_state"] == "deploy-failed"
        assert "deploy-failed" in result["overlays"]

    def test_deploy_crashed(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        data = json.loads((FIXTURES / "deploy_crashed.json").read_text())

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            return_value=data,
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["deploy_state"] == "deploy-failed"
        assert "deploy-failed" in result["overlays"]

    def test_no_deployments(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        data = json.loads((FIXTURES / "deploy_empty.json").read_text())

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            return_value=data,
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["deploy_state"] == "none"
        assert "railway_no_project" in result["warnings"]

    def test_token_missing_returns_unknown(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        result = collect_railway_signals(project_id="proj-1", token=None)

        assert result["deploy_state"] == "unknown"
        assert "railway_unknown" in result["warnings"]

    def test_network_failure_unknown_safe(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            side_effect=OSError("timeout"),
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["deploy_state"] == "unknown"
        assert "railway_unknown" in result["warnings"]

    def test_http_timeout_unknown_safe(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            side_effect=TimeoutError("http timeout"),
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["deploy_state"] == "unknown"
        assert "railway_unknown" in result["warnings"]

    def test_last_deploy_at_from_latest(self) -> None:
        from work_state.signal_collectors.railway import collect_railway_signals

        data = json.loads((FIXTURES / "deploy_failed.json").read_text())

        with patch(
            "work_state.signal_collectors.railway._railway_query",
            return_value=data,
        ):
            result = collect_railway_signals(project_id="proj-1", token="test-token")  # noqa: S106

        assert result["last_deploy_at"] == "2026-05-20T10:00:00Z"
