"""
app/utils/anti_flood.py

Per-user Telegram bot flood/spam protection.

Telegram delivers messages from users at whatever rate the user taps.
This module enforces per-user message rate limits inside the bot process,
preventing a single account from overloading handlers.

Usage (in any handler):
    from app.utils.anti_flood import check_flood

    async def my_handler(update, context):
        if await check_flood(update, context):
            return   # silently drop — flood warning already sent once
        ...

Design:
  - In-memory sliding window per (user_id, bot_type).
  - First violation: sends a warning to the user.
  - Subsequent violations within the window: silent drop (no reply spam).
  - Window and max-message count configurable via constants below.
  - Thread-safe for asyncio (single-threaded event loop).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Deque

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FLOOD_WINDOW_SECONDS = 10       # rolling window length
FLOOD_MAX_MESSAGES   = 5        # allowed messages per window per user
WARN_COOLDOWN        = 30       # seconds between flood warnings to same user
# ---------------------------------------------------------------------------


class _UserWindow:
    __slots__ = ("timestamps", "last_warned")

    def __init__(self) -> None:
        self.timestamps: Deque[float] = deque()
        self.last_warned: float = 0.0


_windows: dict[int, _UserWindow] = {}


def _evict_old(window: _UserWindow, now: float) -> None:
    cutoff = now - FLOOD_WINDOW_SECONDS
    while window.timestamps and window.timestamps[0] < cutoff:
        window.timestamps.popleft()


def is_flooding(user_id: int) -> tuple[bool, bool]:
    """
    Record a message from user_id and return (flooded, should_warn).

    flooded     — True if the user has exceeded the rate limit.
    should_warn — True if we should send a warning reply (respects cooldown).
    """
    now = time.monotonic()
    if user_id not in _windows:
        _windows[user_id] = _UserWindow()

    uw = _windows[user_id]
    _evict_old(uw, now)
    uw.timestamps.append(now)

    if len(uw.timestamps) <= FLOOD_MAX_MESSAGES:
        return False, False  # within limit

    # Over limit — check warning cooldown
    flooded = True
    should_warn = (now - uw.last_warned) >= WARN_COOLDOWN
    if should_warn:
        uw.last_warned = now
    return flooded, should_warn


async def check_flood(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    Convenience coroutine for use in handlers.

    Returns True (and optionally warns the user) when the user is flooding.
    The handler should return immediately when this returns True.
    """
    user = update.effective_user
    if user is None:
        return False

    flooded, should_warn = is_flooding(user.id)
    if not flooded:
        return False

    logger.warning(
        "ANTI-FLOOD: user %s (%s) is flooding. Messages in window: %d",
        user.id,
        user.username or "no-username",
        len(_windows.get(user.id, _UserWindow()).timestamps),
    )

    if should_warn:
        msg = update.message or (update.callback_query and update.callback_query.message)
        if msg:
            try:
                await msg.reply_text(
                    f"⚠️ *Spam ကာကွယ်မှု*\n\n"
                    f"တစ်ကြိမ်ကြာ ဆက်ဆောင်ရွက်ရန် ကျေးဇူးပြု၍ {FLOOD_WINDOW_SECONDS} စက္ကန့် ခနစောင့်ပါ။",
                    parse_mode="Markdown",
                )
            except Exception:
                pass  # never let flood protection crash the bot

    return True


def cleanup_stale_windows(older_than: float = 300.0) -> int:
    """
    Remove entries not seen in `older_than` seconds.
    Call periodically (e.g., via APScheduler or bot job_queue).
    Returns number of entries removed.
    """
    now = time.monotonic()
    cutoff = now - older_than
    stale = [uid for uid, uw in _windows.items()
             if not uw.timestamps or uw.timestamps[-1] < cutoff]
    for uid in stale:
        del _windows[uid]
    return len(stale)
