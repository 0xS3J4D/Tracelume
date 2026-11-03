"""Protection for a local web app without login.

- Host header allow-list blocks DNS-rebinding attacks (a malicious site resolving its own
  domain to 127.0.0.1 to read the API).
- State-changing requests must come from Tracelume's own origin: browsers always send an
  Origin header on cross-site POST/PUT/PATCH/DELETE, so a foreign page cannot use the API (CSRF).
- Conservative security headers on every response.
"""

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from tracelume.config import get_settings

SAFE = {"GET", "HEAD", "OPTIONS"}
CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'self'"
)


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        allowed = {h.strip().lower() for h in get_settings().allowed_hosts.split(",") if h.strip()}
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
        if "*" not in allowed and host not in allowed:
            return JSONResponse({"detail": "host not allowed"}, status_code=400)
        if request.method not in SAFE:
            origin = request.headers.get("origin")
            if (
                origin
                and urlparse(origin).netloc.lower() != (request.headers.get("host") or "").lower()
            ):
                return JSONResponse({"detail": "cross-site request blocked"}, status_code=403)
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if not request.url.path.startswith("/api/"):
            resp.headers.setdefault("Content-Security-Policy", CSP)
        return resp
