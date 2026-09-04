"""
app/utils/numbers.py
====================
Myanmar ↔ English number normalization utility.

Myanmar digits: ၀၁၂၃၄၅၆၇၈၉
English digits: 0123456789

Supports:
  - Myanmar single digit:  "၃"  → 3
  - Myanmar multi-digit:   "၁၀" → 10
  - English:               "25" → 25
  - Mixed not supported (rejected with friendly error)
"""

from __future__ import annotations

MYANMAR_DIGITS = "၀၁၂၃၄၅၆၇၈၉"
ENGLISH_DIGITS = "0123456789"

# Map each Myanmar digit character to its English equivalent
_MM_TO_EN: dict[str, str] = {
    mm: en for mm, en in zip(MYANMAR_DIGITS, ENGLISH_DIGITS)
}


def myanmar_to_english(text: str) -> str:
    """
    Convert a string of Myanmar digits to English digit string.
    Non-Myanmar-digit characters are left unchanged.

    Example: "၁၀" → "10"
    """
    return "".join(_MM_TO_EN.get(ch, ch) for ch in text)


def normalize_number(text: str) -> int | None:
    """
    Normalize a user-entered number string (Myanmar or English digits)
    into a Python int.

    Returns:
        int  — if the input is a valid positive integer
        None — if the input is invalid

    Examples:
        "3"   → 3
        "၃"   → 3
        "10"  → 10
        "၁၀"  → 10
        "abc" → None
        ""    → None
        "0"   → None  (not a positive quantity)
        "-1"  → None
    """
    if not text or not text.strip():
        return None

    cleaned = text.strip()

    # Convert Myanmar digits to English digits
    converted = myanmar_to_english(cleaned)

    # After conversion, must consist entirely of digits
    if not converted.isdigit():
        return None

    value = int(converted)
    if value <= 0:
        return None

    return value


def format_mmk(amount: int) -> str:
    """Format an integer as MMK currency string with comma separators."""
    return f"{amount:,} MMK"
