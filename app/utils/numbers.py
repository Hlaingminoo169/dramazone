"""
app/utils/numbers.py

Myanmar ↔ English digit conversion and numeric input validation.

Supports:
  - English digits:  0-9
  - Myanmar digits:  ၀-၉  (Unicode U+1040..U+1049)

Usage:
    from app.utils.numbers import parse_myanmar_int

    parse_myanmar_int("၃")   → 3
    parse_myanmar_int("10")  → 10
    parse_myanmar_int("abc") → None
"""
from __future__ import annotations

from typing import Optional

# Myanmar digit → ASCII digit mapping
_MYANMAR_TO_ENGLISH = str.maketrans(
    "၀၁၂၃၄၅၆၇၈၉",
    "0123456789",
)


def myanmar_to_english(text: str) -> str:
    """
    Translate Myanmar Unicode digits in `text` to their ASCII equivalents.

    Non-digit characters are left unchanged.
    """
    return text.translate(_MYANMAR_TO_ENGLISH)


def parse_myanmar_int(text: str) -> Optional[int]:
    """
    Parse a user-supplied number string that may contain Myanmar digits.

    Returns:
        The integer value if the input represents a valid positive integer.
        None if the input is invalid (letters, negative, decimal, empty, etc.)

    Rules:
        - Converts Myanmar digits first.
        - Must be a pure integer (no decimal point, no letters).
        - Must be positive (> 0).
    """
    if not text or not text.strip():
        return None

    converted = myanmar_to_english(text.strip())

    # Must consist entirely of digits after conversion.
    if not converted.isdigit():
        return None

    value = int(converted)

    # Reject zero and negative (though isdigit already rules out negatives).
    if value <= 0:
        return None

    return value
