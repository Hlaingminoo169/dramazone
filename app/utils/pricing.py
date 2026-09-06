"""
app/utils/pricing.py

Centralised pricing configuration.

All pricing logic lives here.
Handlers and services import from this module — pricing is NEVER
duplicated or hard-coded elsewhere.

Current packages:
    1 ကား  →  1,500 MMK
    3 ကား  →  3,500 MMK
    5 ကား  →  5,000 MMK
"""
from __future__ import annotations

from typing import Dict, Optional, List, Tuple

# ── Package table ─────────────────────────────────────────────────────────────
# Key   : quantity (number of movies)
# Value : price in MMK (integer)
PACKAGES: Dict[int, int] = {
    1: 1_500,
    3: 3_500,
    5: 5_000,
}


def get_package_price(quantity: int) -> Optional[int]:
    """
    Return the price in MMK for the given quantity, or None if
    the quantity is not a configured package.

    Args:
        quantity: Number of movies requested.

    Returns:
        Price in MMK, or None if not a valid package.
    """
    return PACKAGES.get(quantity)


def get_all_packages() -> List[Tuple[int, int]]:
    """
    Return all packages as a sorted list of (quantity, price) tuples.
    """
    return sorted(PACKAGES.items())


def format_price(amount: int) -> str:
    """
    Format a price for display.

    Example:
        format_price(1500)   → "1,500 MMK"
        format_price(5000)   → "5,000 MMK"
    """
    return f"{amount:,} MMK"


def is_valid_package(quantity: int) -> bool:
    """Return True if the quantity matches a configured package."""
    return quantity in PACKAGES
