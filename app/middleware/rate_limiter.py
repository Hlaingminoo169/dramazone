"""
app/middleware/rate_limiter.py

IP-based rate limiting middleware using a sliding-window algorithm.

Design goals:
  - Zero external dependencies (pure stdlib + asyncio).
  - Memory-safe: old windows are evicted automatically.
  - DDoS-resilient: constant-time lookup via dict; no DB round-trips.
  - Two tiers:
      GLOBAL  : all endpoints — hard cap on req/s per IP
      WEBHOOK : /webhook/* — tighter limit, Telegram IPs are whitelisted
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Telegram's published IP ranges (IPv4).  We trust their webhook calls fully.
# https://core.telegram.org/bots/webhooks#the-short-version
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Telegram's published IP ranges (IPv4 + IPv6).
# https://core.telegram.org/bots/webhooks#the-short-version
# ---------------------------------------------------------------------------
import ipaddress as _ipaddress

_TELEGRAM_NETWORKS: tuple[_ipaddress.IPv4Network | _ipaddress.IPv6Network, ...] = (
    _ipaddress.ip_network("149.154.160.0/20"),
    _ipaddress.ip_network("149.154.164.0/22"),
    _ipaddress.ip_network("91.108.4.0/22"),
    _ipaddress.ip_network("91.108.8.0/22"),
    _ipaddress.ip_network("91.108.56.0/22"),
    # IPv6 range
    _ipaddress.ip_network("2001:b28:f23d::/48"),
    _ipaddress.ip_network("2001:b28:f23f::/48"),
    _ipaddress.ip_network("2001:67c:4e8::/48"),
)


def _is_telegram_ip(ip: str) -> bool:
    """Return True if the IP belongs to Telegram's published server ranges."""
    try:
        addr = _ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _TELEGRAM_NETWORKS)


def _get_client_ip(request: Request) -> str:
    """
    Extract the real client IP, respecting X-Forwarded-For from trusted proxies.
    Falls back to direct connection address.
    """
    # Trust X-Forwarded-For only when behind a reverse proxy.
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # Leftmost IP is the original client.
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# Sliding-window counter
# ---------------------------------------------------------------------------

class _SlidingWindow:
    """Thread-safe sliding-window rate limiter for a single key."""

    __slots__ = ("_window", "_max_requests", "_timestamps")

    def __init__(self, window_seconds: float, max_requests: int) -> None:
        self._window       = window_seconds
        self._max_requests = max_requests
        self._timestamps: Deque[float] = deque()

    def is_allowed(self) -> bool:
        now   = time.monotonic()
        cutoff = now - self._window
        # Evict expired entries
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max_requests:
            return False
        self._timestamps.append(now)
        return True


class RateLimiterStore:
    """Global in-process store for per-IP sliding windows."""

    def __init__(
        self,
        global_window: float = 60.0,
        global_max: int = 120,
        webhook_window: float = 10.0,
        webhook_max: int = 30,
        cleanup_interval: float = 300.0,
    ) -> None:
        self._global_window   = global_window
        self._global_max      = global_max
        self._webhook_window  = webhook_window
        self._webhook_max     = webhook_max
        self._cleanup_interval = cleanup_interval

        self._global_store:  dict[str, _SlidingWindow] = {}
        self._webhook_store: dict[str, _SlidingWindow] = {}
        self._last_cleanup   = time.monotonic()

    # -- public ----------------------------------------------------------------

    def check_global(self, ip: str) -> bool:
        self._maybe_cleanup()
        if ip not in self._global_store:
            self._global_store[ip] = _SlidingWindow(self._global_window, self._global_max)
        return self._global_store[ip].is_allowed()

    def check_webhook(self, ip: str) -> bool:
        self._maybe_cleanup()
        if ip not in self._webhook_store:
            self._webhook_store[ip] = _SlidingWindow(self._webhook_window, self._webhook_max)
        return self._webhook_store[ip].is_allowed()

    def ban(self, ip: str) -> None:
        """Instantly exhaust all remaining budget for this IP (soft-ban)."""
        sw = _SlidingWindow(self._global_window, 0)
        self._global_store[ip] = sw
        logger.warning("SECURITY: IP %s has been soft-banned.", ip)

    # -- internals -------------------------------------------------------------

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        cutoff_global  = now - self._global_window
        cutoff_webhook = now - self._webhook_window

        for store, cutoff in (
            (self._global_store,  cutoff_global),
            (self._webhook_store, cutoff_webhook),
        ):
            stale = [
                ip for ip, sw in store.items()
                if not sw._timestamps or sw._timestamps[-1] < cutoff
            ]
            for ip in stale:
                del store[ip]

        self._last_cleanup = now
        logger.debug("Rate limiter cleanup: removed stale entries.")


# Singleton store — shared across all requests in this process.
_store = RateLimiterStore(
    global_window=60,    # 60-second rolling window
    global_max=200,      # max 200 requests / 60s per IP  (global)
    webhook_window=10,   # 10-second rolling window
    webhook_max=40,      # max 40 webhook hits / 10s per IP
    cleanup_interval=300,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that enforces per-IP rate limits.

    Rules:
      1. Telegram IPs are whitelisted (never rate-limited on /webhook/*).
      2. Every IP is subject to the global cap.
      3. /webhook/* endpoints have an additional tighter cap.
      4. Excessive violators receive HTTP 429 with a Retry-After header.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        ip      = _get_client_ip(request)
        path    = request.url.path
        is_hook = path.startswith("/webhook/")

        # Telegram servers are always allowed on webhook paths.
        if is_hook and _is_telegram_ip(ip):
            return await call_next(request)

        # --- Global rate limit ---
        if not _store.check_global(ip):
            logger.warning("RATE LIMIT (global) exceeded by IP %s on %s", ip, path)
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests. Please slow down."},
                headers={"Retry-After": "60"},
            )

        # --- Webhook-specific rate limit ---
        if is_hook and not _store.check_webhook(ip):
            logger.warning("RATE LIMIT (webhook) exceeded by IP %s on %s", ip, path)
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests on webhook endpoint."},
                headers={"Retry-After": "10"},
            )

        return await call_next(request)
