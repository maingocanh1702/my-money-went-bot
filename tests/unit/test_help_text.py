"""/help is the only place most people will ever read about what the bot can do.

Two things it kept getting wrong: a command shipped without ever reaching the
list, and Zalo carrying a second hand-written copy of that list — hardcoded in
Vietnamese, so `/lang` did nothing there and every addition had to be remembered
twice. These tests hold both shut.
"""
import pathlib
import re

import pytest

import i18n.core as core
from i18n.core import t
from i18n.vi import STRINGS as VI
from i18n.en import STRINGS as EN


@pytest.fixture
def lang(monkeypatch):
    """Switch the language without persisting it.

    set_lang writes the choice back to the sheet, which in a test means reaching
    for real Google credentials — so the cache is set directly instead. What is
    under test is which strings `t()` returns, not how the preference is stored.
    """
    def _set(code):
        monkeypatch.setattr(core, "_lang_cache", code)
    return _set


def _slash_commands(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w/])(/[a-z]+)", text))


def _main_py() -> str:
    return (pathlib.Path(__file__).resolve().parents[2] / "main.py").read_text()


# ── the MCC editing commands are discoverable ────────────────────────────────

@pytest.mark.parametrize("strings", [VI, EN])
def test_help_documents_every_mcc_editing_command(strings):
    """They are typed into a screen, not slash commands, so /help is the only
    place they can be found at all."""
    help_text = strings["help"]
    for verb in ("ren ", "del ", "skip ", "unskip "):
        assert verb in help_text, f"{verb!r} missing from help"
    assert "5411" in help_text, "the add/re-point example is missing"


# ── the two languages stay in step ───────────────────────────────────────────

def test_both_languages_list_the_same_commands():
    """A command added to one language and forgotten in the other is invisible
    to half the users."""
    assert _slash_commands(VI["help"]) == _slash_commands(EN["help"])


def _dispatched_commands() -> set[str]:
    """Every command `_handle_command` actually answers, read off its dispatch
    table rather than copied into this file — a list copied here would drift the
    same way the Zalo one did."""
    src = _main_py()
    block = re.search(
        r"^async def _handle_command\b.*?(?=^async def |^def )",
        src, re.S | re.M,
    )
    assert block, "_handle_command not found — did the dispatch move?"
    found: set[str] = set()
    for expr in re.findall(r'cmd (?:==|in) *(\([^)]*\)|"[^"]*")', block.group(0)):
        found |= set(re.findall(r'"(/[a-z]+)"', expr))
    assert len(found) > 5, f"parsed too few commands: {found}"
    return found


@pytest.mark.parametrize("strings", [VI, EN])
def test_help_lists_every_command_the_bot_answers(strings):
    """The list is only useful if it is complete. /help and /start are the help
    itself, so they are the only ones allowed to be absent from it."""
    listed = _slash_commands(strings["help"])
    missing = _dispatched_commands() - listed - {"/help", "/start"}
    assert not missing, f"answered but not in /help: {sorted(missing)}"


# ── one source, both channels ────────────────────────────────────────────────

def test_zalo_help_follows_the_language_setting(lang):
    """It used to be a hardcoded Vietnamese string in main.py, so /lang was
    silently ignored on Zalo."""
    lang("en")
    assert "credit-card cashback" in t("help")
    lang("vi")
    assert "cashback thẻ tín dụng" in t("help")


def test_zalo_note_explains_the_numbered_replies_in_both_languages():
    """The one thing Zalo needs that Telegram does not."""
    assert "reply" in VI["help.zalo_note"].lower()
    assert "number" in EN["help.zalo_note"].lower()


def test_main_no_longer_carries_a_second_copy_of_the_command_list():
    assert "- /keywords — Quản lý keyword auto-category" not in _main_py(), (
        "the hardcoded Zalo command list is back; it will drift from i18n again"
    )
