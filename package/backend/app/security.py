"""Shared runtime security controls for every application entry point."""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from collections import OrderedDict, deque
from typing import Callable, Deque, Dict, Iterable, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


_INSECURE_SECRET_KEYS = {
    "",
    "your-secret-key-change-this-in-production",
    "replace-with-a-random-secret",
    "please-change-this-to-a-random-string-32-chars",
}
_INSECURE_ADMIN_PASSWORDS = {
    "",
    "admin123",
    "replace-with-a-strong-password",
    "please-change-this-password",
}


def is_production() -> bool:
    return settings.ENVIRONMENT.strip().lower() in {"prod", "production"}


def validate_runtime_security() -> None:
    """Fail closed when a production process starts with unsafe credentials."""
    if not is_production():
        return

    errors = []
    if settings.SECRET_KEY.strip() in _INSECURE_SECRET_KEYS or len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be a random value of at least 32 characters")

    password_hash = (settings.ADMIN_PASSWORD_HASH or "").strip()
    password = settings.ADMIN_PASSWORD.strip()
    if not password_hash and (
        password in _INSECURE_ADMIN_PASSWORDS or len(password) < 12
    ):
        errors.append("ADMIN_PASSWORD must contain at least 12 characters or ADMIN_PASSWORD_HASH must be set")

    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


def get_cors_origins() -> list[str]:
    return [item.strip() for item in settings.CORS_ORIGINS.split(",") if item.strip()]


def validate_ai_base_url(
    base_url: str,
    *,
    allow_private: Optional[bool] = None,
    resolver: Callable[..., Iterable[Tuple]] = socket.getaddrinfo,
) -> str:
    """Reject credential-bearing, non-HTTPS, and private AI endpoints by default."""
    value = (base_url or "").strip().rstrip("/")
    parsed = urlparse(value)
    private_allowed = settings.ALLOW_PRIVATE_AI_ENDPOINTS if allow_private is None else allow_private

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("AI Base URL must be a valid HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("AI Base URL must not contain embedded credentials")
    if parsed.scheme != "https" and not private_allowed:
        raise ValueError("AI Base URL must use HTTPS")

    if private_allowed:
        return value

    try:
        addresses = {
            item[4][0]
            for item in resolver(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise ValueError(f"AI Base URL host could not be resolved: {parsed.hostname}") from exc

    if not addresses:
        raise ValueError(f"AI Base URL host could not be resolved: {parsed.hostname}")

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise ValueError("AI Base URL resolved to an invalid address") from exc
        if not ip.is_global:
            raise ValueError("AI Base URL must not resolve to a private or reserved address")

    return value


class SlidingWindowRateLimiter:
    """Small in-process limiter suitable for low-volume administrator actions."""

    def __init__(self, attempts: int, window_seconds: int, max_keys: int = 10_000) -> None:
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._events: OrderedDict[str, Deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        expired = []
        for key, events in self._events.items():
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                expired.append(key)
        for key in expired:
            self._events.pop(key, None)
        while len(self._events) > self.max_keys:
            self._events.popitem(last=False)

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            events = self._events.get(key)
            if events and len(events) >= self.attempts:
                retry_after = max(1, int(self.window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            events = self._events.setdefault(key, deque())
            events.append(now)
            self._events.move_to_end(key)
            while len(self._events) > self.max_keys:
                self._events.popitem(last=False)

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


admin_login_limiter = SlidingWindowRateLimiter(attempts=5, window_seconds=300)


def admin_login_key(request: Request, username: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{username.strip().lower()}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
