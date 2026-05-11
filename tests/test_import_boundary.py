"""Smoke tests for import-linter boundary enforcement (ADR-0001).

Verifies that:
  1. `.importlinter` config exists at repo root.
  2. `lint-imports` runs clean on current codebase.
  3. The real config declares the `core ↛ markets` contract (static check).
  4. The import-linter tool catches violations — proven in an isolated
     mini-project under `tmp_path`, NOT by mutating the real `core/` package.

The isolated tmp_path approach avoids the race / contamination risk that
arises if a test writes a violating file into the real package tree and
crashes (or runs in parallel) before cleanup.
"""

from __future__ import annotations

import configparser
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_importlinter_config_exists() -> None:
    """`.importlinter` config file must exist at repo root."""
    config = REPO_ROOT / ".importlinter"
    assert config.exists(), ".importlinter config missing — ADR-0001 boundary not enforced"


def test_importlinter_runs_clean() -> None:
    """`lint-imports` must pass on current codebase (no violations)."""
    if shutil.which("lint-imports") is None:
        pytest.skip("lint-imports not installed in this environment")

    result = subprocess.run(
        ["lint-imports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (
        result.returncode == 0
    ), f"lint-imports failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_real_config_declares_core_markets_contract() -> None:
    """Static check: real `.importlinter` declares the ADR-0001 contract
    with the EXACT module mapping core → markets.

    Parses the config via configparser and inspects the specific contract
    section. Verifies:
      - section `[importlinter:contract:core-must-not-import-markets]` exists
      - `type == 'forbidden'`
      - `'core'` is in `source_modules` (as a parsed module name, not a
        substring lurking in comments)
      - `'markets'` is in `forbidden_modules`

    Substring matching on the whole config text is too permissive — an edit
    that weakens the contract (e.g. swaps the source module to `handlers`)
    could still leave decoy `core`/`markets` tokens in other sections and
    pass a naive check. Parsing the contract section explicitly closes that
    gap.
    """
    config = configparser.ConfigParser()
    config.read(REPO_ROOT / ".importlinter", encoding="utf-8")

    section = "importlinter:contract:core-must-not-import-markets"
    assert (
        section in config.sections()
    ), f"Missing contract section [{section}] — ADR-0001 boundary not declared"

    contract = config[section]
    assert (
        contract.get("type") == "forbidden"
    ), f"Contract type must be 'forbidden', got {contract.get('type')!r}"

    # source_modules / forbidden_modules are multi-line INI values; the
    # continuation lines are indented. configparser joins them with newlines;
    # .split() collapses whitespace and yields the bare module names.
    source_modules = (contract.get("source_modules") or "").split()
    forbidden_modules = (contract.get("forbidden_modules") or "").split()

    assert source_modules == [
        "core"
    ], f"Contract source_modules must be exactly ['core'], got {source_modules}"
    assert forbidden_modules == [
        "markets"
    ], f"Contract forbidden_modules must be exactly ['markets'], got {forbidden_modules}"


def test_importlinter_blocks_violation_in_isolated_project(tmp_path: Path) -> None:
    """Negative test: import-linter catches a violation in a synthetic
    mini-project under `tmp_path`.

    Builds a self-contained project mirroring the boundary rule, plants a
    deliberate violation, runs `lint-imports` against the synthetic config,
    and asserts the tool flags it. Does NOT mutate the real `core/` package
    — so no race, no orphan-file risk, no accidental commit possible.

    If this test fails, the import-linter library itself is not enforcing
    the rule pattern we depend on — DO NOT MERGE.
    """
    if shutil.which("lint-imports") is None:
        pytest.skip("lint-imports not installed in this environment")

    # Build isolated mini-project
    core_pkg = tmp_path / "iso_core"
    markets_pkg = tmp_path / "iso_markets"
    core_pkg.mkdir()
    markets_pkg.mkdir()
    (core_pkg / "__init__.py").write_text("", encoding="utf-8")
    (markets_pkg / "__init__.py").write_text("", encoding="utf-8")
    (markets_pkg / "sub.py").write_text("VALUE = 1\n", encoding="utf-8")

    # Plant the violation: core imports markets
    (core_pkg / "violator.py").write_text(
        "from iso_markets import sub  # noqa: F401 — deliberate violation\n",
        encoding="utf-8",
    )

    # Synthetic .importlinter mirroring the real ADR-0001 rule shape
    (tmp_path / ".importlinter").write_text(
        "[importlinter]\n"
        "root_packages =\n"
        "    iso_core\n"
        "    iso_markets\n"
        "\n"
        "[importlinter:contract:iso-core-must-not-import-markets]\n"
        "name = iso_core MUST NOT import from iso_markets\n"
        "type = forbidden\n"
        "source_modules =\n"
        "    iso_core\n"
        "forbidden_modules =\n"
        "    iso_markets\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["lint-imports"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0, (
        "import-linter FAILED to catch the synthetic core → markets violation.\n"
        "The boundary-enforcement mechanism we rely on for ADR-0001 is broken.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    # Confirm the violation message names the contract
    output = (result.stdout + result.stderr).lower()
    assert (
        "iso_core" in output and "iso_markets" in output
    ), f"import-linter output did not name the violating contract:\n{output}"
