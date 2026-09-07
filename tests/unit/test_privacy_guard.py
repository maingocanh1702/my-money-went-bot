"""The guard that keeps the maintainer's own data out of the public repo.

The hash list only catches what someone already knew to ban. It passed clean
for weeks while seven files carried the maintainer's macOS home path, because
a username is not a token anyone thought to write down — so the shape rules,
not the hash list, are what catch the leak nobody predicted. These tests cover
the shape rules and assert the tree is clean right now.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "scripts" / "check_no_personal_data.py"

_spec = importlib.util.spec_from_file_location("privacy_guard", GUARD)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _flagged(text: str) -> list[str]:
    return [n for n in set(guard.HOME_PATH.findall(text))
            if n.lower() not in guard.ALLOWED_HOME_NAMES]


@pytest.mark.parametrize("text,name", [
    ("You are working in `/Users/someperson/Projects/My Money Went Bot`", "someperson"),
    ('cd "/Users/someperson/Projects/My Money Went Bot"', "someperson"),
    ("/home/someperson/checkout", "someperson"),
    (r"C:\Users\someperson\checkout", "someperson"),
])
def test_a_real_home_directory_is_flagged(text, name):
    """A home directory names the person who owns the machine."""
    assert _flagged(text) == [name]


@pytest.mark.parametrize("text", [
    "/home/ubuntu/my-money-went-bot",     # what the VPS docs actually deploy to
    "/Users/YourName/projects/bot",       # a placeholder a reader substitutes
    "/home/runner/work/repo",             # GitHub Actions
    "/home/root/x",
])
def test_deploy_targets_and_placeholders_are_not_flagged(text):
    assert _flagged(text) == []


def test_banned_literals_are_stored_only_as_hashes():
    """Writing a bank account number into the guard that protects it would
    simply publish it again."""
    for digest in guard.BANNED_TOKEN_HASHES:
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)


def test_the_tracked_tree_is_clean_right_now():
    """The guard is the build step; this is the same check, from the suite, so
    a leak fails locally before it reaches CI."""
    result = subprocess.run(
        [sys.executable, str(GUARD)], cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
