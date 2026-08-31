"""
utils.py — shared helpers.

parse_money: the ONE money-input parser for every handler that accepts a
typed amount (Telegram + Zalo). Understands what people actually type:

    "3000000", "3,000,000", "3.000.000"  → 3000000.0
    "100.50", "1,5"                       → 100.5, 1.5   (decimals)
    "-100.000đ"                           → -100000.0    (negative)
    "500k", "2k5"                         → 500000, 2500
    "3tr", "3tr5", "1.5tr", "2 triệu"     → 3000000, 3500000, 1500000, 2000000
    "1m", "1m2", "1 tỷ"                   → 1000000, 1200000, 1000000000

Returns float | None. Rationale: the old per-handler digit-stripping made
"500k" silently become 500đ and garbage silently become 0đ — this parser
understands the shorthand and rejects what it can't read.
"""
from __future__ import annotations

import re
import unicodedata

_UNIT_MULTIPLIERS = {
    "k":     1_000,
    "nghin": 1_000,
    "ngan":  1_000,
    "tr":    1_000_000,
    "trieu": 1_000_000,
    "m":     1_000_000,
    "ty":    1_000_000_000,
}


def _parse_shorthand(s: str) -> float | None:
    """Parse Vietnamese money shorthand ('500k', '3tr5', '1.5tr', '2trieu').

    `s` must already be lowercased, diacritics-stripped, whitespace-free.
    Returns the VND value, or None when `s` is not shorthand-shaped.
    """
    m = re.fullmatch(r"(\d+)(?:[.,](\d+))?(k|nghin|ngan|trieu|tr|m|ty)(\d{1,2})?", s)
    if not m:
        return None
    whole, frac, unit, tail = m.groups()
    value = float(whole)
    if frac:
        value += float(f"0.{frac}")
    if tail:  # "3tr5" → 3.5tr, "2k5" → 2.5k
        value += float(f"0.{tail}")
    return value * _UNIT_MULTIPLIERS[unit]


def parse_money(text: str) -> float | None:
    """Parse a typed money amount. Returns float or None when invalid."""
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None

    negative = raw.startswith(("-", "−"))

    # ── Shorthand pass: 500k / 3tr / 3tr5 / 1m2 / 2 triệu / 1 tỷ ──
    norm = unicodedata.normalize("NFD", raw.lower())
    norm = re.sub(r"[\u0300-\u036f]", "", norm)   # strip diacritics (triệu → trieu)
    norm = norm.replace("đ", "d").lstrip("-−")
    norm = re.sub(r"(vnd|dong|d)\s*$", "", norm)  # drop trailing currency suffix
    norm = re.sub(r"\s+", "", norm)
    shorthand = _parse_shorthand(norm)
    if shorthand is not None:
        return -shorthand if negative else shorthand

    # ── Plain-number pass: separators + decimals ──
    # Strict: after normalization (currency suffix + whitespace removed) the
    # remainder must be digits/separators only. "5tr/tháng" or "abc100" is
    # rejected instead of being digit-stripped into a wrong number.
    if not re.fullmatch(r"[\d.,]+", norm):
        return None
    s = norm
    # If it has multiple dots/commas → thousands separators, strip them
    if s.count(".") > 1 or s.count(",") > 1:
        s = s.replace(".", "").replace(",", "")
    elif "," in s and "." in s:
        # 1,000.50 or 1.000,50 — last separator is decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3:
            s = s.replace(",", "")  # 1,000 = thousands
        else:
            s = s.replace(",", ".")  # 1,5 = decimal
    elif "." in s:
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            s = s.replace(".", "")  # 1.000 = VND thousands
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        value = float(s)
        return -value if negative else value
    except ValueError:
        return None


def parse_budget_amount(text: str) -> int | None:
    """Parse a budget/limit amount: non-negative whole VND.

    Accepts everything parse_money accepts; rejects negatives.
    Returns int VND or None. Used by /allocate, /manage and the Zalo
    equivalents — '0' stays valid (tracking-only)."""
    val = parse_money(text)
    if val is None or val < 0:
        return None
    return int(round(val))
