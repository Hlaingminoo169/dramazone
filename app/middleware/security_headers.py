"""
app/middleware/security_headers.py

HTTP security headers middleware.

Adds industry-standard headers to every response to protect against:
  - Clickjacking         (X-Frame-Options)
  - MIME sniffing        (X-Content-Type-Options)
  - XSS                  (X-XSS-Protection, CSP)
  - Information leakage  (Server, X-Powered-By stripped)
  - Protocol downgrade   (HSTS on HTTPS deployments)
  - Referrer leakage     (Referrer-Policy)
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_SECURITY_HEADERS: dict[str, str] = {
    # Prevent this app from being embedded in iframes (clickjacking)
    "X-Frame-Options": "DENY",
    # Prevent MIME-type sniffing
    "X-Content-Type-Options": "nosniff",
    # Legacy XSS filter (modern browsers use CSP instead)
    "X-XSS-Protection": "1; mode=block",
    # Strict CSP — this is a pure API/webhook server; no HTML is served
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    # Don't send the full URL as Referer
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Restrict browser features
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Only allow HTTPS for the next year (enable on production only)
    # Uncomment when you have TLS termination set up:
    # "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

_STRIP_HEADERS: tuple[str, ...] = (
    "Server",
    "X-Powered-By",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers and remove information-leaking headers from every response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Add protective headers.
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value

        # Remove headers that reveal implementation details.
        for header in _STRIP_HEADERS:
            response.headers.pop(header, None)

        return response
