"""Key-parity invariant: every key in VI MUST exist in EN, and vice versa.

This is the CI-level guarantee from feature-i18n.md acceptance criteria:
"All keys exist in both vi.py and en.py (CI test)".

Any divergence is a bug — fix by adding the missing key, not by skipping.
"""

from __future__ import annotations

from i18n import EN, VI


def test_every_vi_key_exists_in_en() -> None:
    missing = sorted(set(VI) - set(EN))
    assert not missing, f"Keys in vi.py but missing in en.py: {missing}"


def test_every_en_key_exists_in_vi() -> None:
    missing = sorted(set(EN) - set(VI))
    assert not missing, f"Keys in en.py but missing in vi.py: {missing}"


def test_no_empty_translations() -> None:
    empty_vi = [k for k, v in VI.items() if not v.strip()]
    empty_en = [k for k, v in EN.items() if not v.strip()]
    assert not empty_vi, f"Empty VI templates: {empty_vi}"
    assert not empty_en, f"Empty EN templates: {empty_en}"


def test_format_placeholders_match_between_locales() -> None:
    """If `vi[key]` references `{name}`, `en[key]` must too (and same set).

    Catches drift where one locale adds a placeholder the other locale lacks
    — that would surface only at runtime when a caller passes kwargs.
    """
    import string

    fmt = string.Formatter()

    def placeholders(template: str) -> set[str]:
        return {field for _, field, _, _ in fmt.parse(template) if field}

    mismatches: list[tuple[str, set[str], set[str]]] = []
    for key in set(VI) & set(EN):
        vi_ph = placeholders(VI[key])
        en_ph = placeholders(EN[key])
        if vi_ph != en_ph:
            mismatches.append((key, vi_ph, en_ph))
    assert not mismatches, f"Placeholder drift: {mismatches}"
