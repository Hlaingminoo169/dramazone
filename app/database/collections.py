"""
app/database/collections.py
─────────────────────────────────────────────────────────────────────────────
MongoDB collection name constants.

Centralising collection names here means:
- No magic strings scattered across the codebase
- Renaming a collection requires changing only this file
- IDE autocomplete works everywhere

All collections are referenced via this module:
    from app.database.collections import ORDERS, SESSIONS, ...
"""

from __future__ import annotations

# Core business collections
USERS: str = "users"
"""Customer / Telegram user profiles."""

MOVIES: str = "movies"
"""VIP movie/content catalog."""

ORDERS: str = "orders"
"""Purchase orders — the central collection."""

# State & session management
SESSIONS: str = "sessions"
"""MongoDB-backed user session state for conversation recovery (req #30)."""

# Security & rate limiting
RATE_LIMITS: str = "rate_limits"
"""TTL-backed rate limit counters per user+action (req #2)."""

# Admin & audit
AUDIT_LOGS: str = "audit_logs"
"""Admin action audit trail (req #5)."""

SETTINGS: str = "settings"
"""Runtime-configurable bot settings (e.g. pricing, payment accounts)."""

# ──────────────────────────────────────────────
# All collection names in a single set for validation/migration tooling
# ──────────────────────────────────────────────
ALL_COLLECTIONS: frozenset[str] = frozenset({
    USERS,
    MOVIES,
    ORDERS,
    SESSIONS,
    RATE_LIMITS,
    AUDIT_LOGS,
    SETTINGS,
})
