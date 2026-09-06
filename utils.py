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
import math

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


def resolve_separators(s: str) -> str | None:
    """Turn a digits-and-separators string into a plain decimal string.

    "." and "," are each a thousands separator in one locale and a decimal
    point in another, so what they mean has to be decided from the shape of
    the number before it is handed to float(). Guessing wrong is not a
    rounding error: float("50.000") is fifty, and the number on the screen was
    fifty thousand.

    The rules, in order:
      * both separators present → whichever appears LAST is the decimal point
      * one separator, repeated → thousands grouping ("1.234.567")
      * one separator, exactly three digits after it → thousands ("50.000",
        "1,000") — no currency this bot handles has three decimal places
      * otherwise → decimal point ("100.50", "1,5")

    Returns None when `s` is not a number, so the caller decides what an
    unreadable amount means rather than inheriting a silent zero.
    """
    s = (s or "").strip()
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    if s[0] in ".,":
        s = "0" + s
    if s[-1] in ".,":
        s = s[:-1]

    dots, commas = s.count("."), s.count(",")
    if dots and commas:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
    elif dots or commas:
        sep = "." if dots else ","
        tail = s.rsplit(sep, 1)[1]
        dec = "" if ((dots or commas) > 1 or len(tail) == 3) else sep
    else:
        dec = ""

    if dec:
        s = s.replace("," if dec == "." else ".", "").replace(dec, ".")
    else:
        s = s.replace(".", "").replace(",", "")

    return s if re.fullmatch(r"\d+(?:\.\d+)?", s) else None


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
        value = -shorthand if negative else shorthand
        return value if math.isfinite(value) else None

    # ── Plain-number pass: separators + decimals ──
    # Strict: after normalization (currency suffix + whitespace removed) the
    # remainder must be digits/separators only. "5tr/tháng" or "abc100" is
    # rejected instead of being digit-stripped into a wrong number.
    resolved = resolve_separators(norm)
    if resolved is None:
        return None
    try:
        value = float(resolved)
    except ValueError:
        return None
    value = -value if negative else value
    return value if math.isfinite(value) else None


def parse_budget_amount(text: str) -> int | None:
    """Parse a budget/limit amount: non-negative whole VND.

    Accepts everything parse_money accepts; rejects negatives.
    Returns int VND or None. Used by /allocate, /manage and the Zalo
    equivalents — '0' stays valid (tracking-only)."""
    val = parse_money(text)
    if val is None or not math.isfinite(val) or val < 0:
        return None
    return int(round(val))
