"""i18n hygiene + user-visible prompt regressions (audit 2026-08-25 round 2)."""
import pytest

from i18n.vi import STRINGS as VI
from i18n.en import STRINGS as EN


def test_vi_en_key_parity():
    """Every key must exist in BOTH languages — t() falls back silently, so a
    missing EN key means a Vietnamese string leaks into the English UI."""
    assert set(VI) == set(EN), (
        f"missing in en: {sorted(set(VI) - set(EN))}; "
        f"missing in vi: {sorted(set(EN) - set(VI))}"
    )


def test_no_literal_backslash_n_in_strings():
    """`\\n` typed as two characters renders literally in chat (the old
    ac.unmapped bug)."""
    for lang, strings in (("vi", VI), ("en", EN)):
        for key, val in strings.items():
            assert "\\n" not in val, f"{lang}:{key} contains a literal backslash-n"


def test_help_key_exists_and_lists_commands():
    for strings in (VI, EN):
        text = strings["help"]
        for cmd in ("/report", "/today", "/manage", "/pending", "/recat"):
            assert cmd in text, f"help text missing {cmd}"


