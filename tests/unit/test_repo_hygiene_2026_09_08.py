"""Guards for the 2026-09-08 audit's infrastructure and documentation gaps.

Documentation drift is invisible until somebody needs the doc, so the two
things that actually drifted — the Python version and the command list — are
checked here rather than trusted.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ─── One Python version, in one place ────────────────────────────

def test_python_version_files_agree():
    """Neither file pinned anything before this; having two that disagree
    would be worse than having none."""
    dotfile = _read(".python-version").strip()
    runtime = _read("runtime.txt").strip()
    assert runtime == f"python-{dotfile}", (
        f".python-version says {dotfile!r}, runtime.txt says {runtime!r}"
    )


def test_ci_takes_the_python_version_from_the_file():
    ci = _read(".github/workflows/ci.yml")
    assert "python-version-file: '.python-version'" in ci
    assert "python-version: '3" not in ci, "CI has gone back to a hard-coded version"


# ─── Actions are pinned the way dependabot.yml claims ────────────

def test_every_action_is_pinned_to_a_commit_sha():
    """dependabot.yml says it 'Keeps SHAs in .github/workflows/ci.yml current'.
    It was keeping floating major tags current instead."""
    floating = []
    for wf in sorted((ROOT / ".github/workflows").glob("*.yml")):
        for ref in re.findall(r"uses:\s*([^\s#]+)", wf.read_text(encoding="utf-8")):
            if "@" not in ref:
                continue
            _, _, version = ref.partition("@")
            if not re.fullmatch(r"[0-9a-f]{40}", version):
                floating.append(f"{wf.name}: {ref}")
    assert not floating, f"not pinned to a SHA: {floating}"


# ─── The lint gate is reproducible outside CI ────────────────────

def test_ruff_is_a_declared_dev_dependency():
    """CONTRIBUTING tells contributors to install requirements-dev.txt and run
    the tests. The lint gate was installed inline in CI and nowhere else."""
    deps = _read("requirements-dev.txt")
    assert re.search(r"^ruff==", deps, re.M), "ruff is not in requirements-dev.txt"
    ci = _read(".github/workflows/ci.yml")
    pinned = re.search(r"^ruff==(\S+)", deps, re.M).group(1)
    inline = re.search(r"pip install ruff==(\S+)", ci)
    if inline:
        assert inline.group(1) == pinned, "CI installs a different ruff than the dev file pins"


# ─── The scheduled workflow cannot go red on a placeholder ───────

def test_cron_workflow_skips_itself_until_bot_url_is_set():
    cron = _read(".github/workflows/cron.yml")
    assert "schedule:" in cron, "the schedule is the point of this workflow"
    assert "YOUR-APP" in cron, "the placeholder is still what upstream ships"
    assert "steps.guard.outputs.skip == 'false'" in cron, \
        "every firing step must be gated on the placeholder guard"
    fired_steps = cron.count("steps.guard.outputs.skip == 'false'")
    assert fired_steps >= 2, "a step that talks to BOT_URL is not gated"


def test_cron_secret_is_not_in_the_workflow_url():
    cron = _read(".github/workflows/cron.yml")
    assert "?secret=" not in cron
    assert "Authorization: Bearer" in cron


# ─── Every command a user can type is documented ─────────────────

def _registered_commands() -> set[str]:
    main_src = _read("main.py")
    found = set()
    for pat in (r'text\.startswith\("(/[a-z_]+)"\)', r'cmd == "(/[a-z_]+)"',
                r'"(/[a-z_]+)"\s*:'):
        found |= set(re.findall(pat, main_src))
    return found


@pytest.mark.parametrize("doc", ["README.md", "README.vi.md"])
def test_every_command_appears_in_both_readmes(doc):
    """/cancel_tx shipped and was documented nowhere — not the EN README, the
    VI README, the wiki, or the changelog. It was the only such command."""
    text = _read(doc)
    missing = sorted(c for c in _registered_commands() if c not in text)
    assert not missing, f"{doc} does not document: {missing}"


def test_every_command_appears_in_the_wiki_command_reference():
    text = _read("docs/wiki/Command-Reference.md")
    missing = sorted(c for c in _registered_commands() if c not in text)
    assert not missing, f"the published wiki does not document: {missing}"


# ─── Every env var the code reads is in .env.example ─────────────

def test_env_example_documents_every_variable_the_code_reads():
    example = _read(".env.example")
    read_vars: set[str] = set()
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "venv/", "tests/", ".autopilot/")):
            continue
        src = py.read_text(encoding="utf-8", errors="ignore")
        read_vars |= set(re.findall(r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]+)"', src))
        read_vars |= set(re.findall(r'os\.getenv\(\s*"([A-Z][A-Z0-9_]+)"', src))
        read_vars |= set(re.findall(r'_env_(?:bool|int)\(\s*"([A-Z][A-Z0-9_]+)"', src))
    # Set by the platform, not by the operator.
    read_vars -= {"PORT", "RAILWAY_ENVIRONMENT", "PYTHONPATH", "TZ", "HOME", "PATH"}
    missing = sorted(v for v in read_vars if v not in example)
    assert not missing, f".env.example does not mention: {missing}"


# ─── The privacy guard no longer hands out targeting hints ───────

def test_banned_digests_carry_no_description():
    """An unsalted SHA-256 of a ten-digit account number is recoverable by
    enumeration; the label told a reader which digest was worth enumerating."""
    src = _read("scripts/check_no_personal_data.py")
    block = re.search(r"BANNED_TOKEN_HASHES = \{\n(.*?)\n\}", src, re.S).group(1)
    labelled = [ln for ln in block.splitlines() if re.search(r'":\s*"', ln)]
    assert not labelled, f"digests still carry descriptions: {labelled[:3]}"


def test_service_accounts_and_hostnames_are_matched_by_shape():
    src = _read("scripts/check_no_personal_data.py")
    assert "GCP_SERVICE_ACCOUNT" in src
    assert "DEPLOY_HOSTNAME" in src
