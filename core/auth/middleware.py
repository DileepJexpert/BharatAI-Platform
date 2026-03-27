"""FastAPI middleware for static API key auth and rate limiting (MVP)."""

import logging
import os
import time
from typing import Any

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Header scheme for dependency injection
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Paths that skip auth entirely
PUBLIC_PATHS: set[str] = {"/health", "/docs", "/openapi.json", "/redoc"}


def _load_api_keys() -> dict[str, str]:
    """Load API key -> app_id mappings from env vars.

    Convention: <APP_ID_UPPER>_API_KEY env var maps to <app_id> slug.
    Example: ASHA_HEALTH_API_KEY=dev-asha-key-001 -> key maps to 'asha_health'
    """
    mapping: dict[str, str] = {}
    for key, value in os.environ.items():
        if key.endswith("_API_KEY") and value:
            # ASHA_HEALTH_API_KEY -> asha_health
            app_id = key[: -len("_API_KEY")].lower()
            mapping[value] = app_id
    return mapping


class AuthMiddleware(BaseHTTPMiddleware):
    """Validates X-API-Key header and enforces rate limits."""

    def __init__(self, app: Any, rate_limit: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.rate_limit = int(os.getenv("RATE_LIMIT_REQUESTS", str(rate_limit)))
        self.window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", str(window_seconds)))
        # key -> list of request timestamps
        self._rate_counters: dict[str, list[float]] = {}

    @property
    def api_keys(self) -> dict[str, str]:
        """Reload keys each request so env changes take effect without restart."""
        return _load_api_keys()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Also skip for /models (read-only info)
        if path == "/models":
            return await call_next(request)

        # Extract API key
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing X-API-Key header"},
            )

        # Validate key
        api_keys = self.api_keys
        if api_key not in api_keys:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"},
            )

        app_id_from_key = api_keys[api_key]

        # Check app_id isolation: if path starts with /{app_id}/,
        # the key must belong to that app
        path_parts = path.strip("/").split("/")
        if path_parts:
            requested_app_id = path_parts[0]
            # Only enforce for app-scoped routes (not /admin, /health, etc.)
            if requested_app_id != app_id_from_key and requested_app_id not in (
                "admin", "health", "models"
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": f"API key for '{app_id_from_key}' cannot access "
                                  f"'{requested_app_id}' resources"
                    },
                )

        # Rate limiting
        if self._is_rate_limited(api_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window_seconds)},
            )

        # Attach app_id to request state for downstream use
        request.state.app_id = app_id_from_key
        request.state.api_key = api_key

        return await call_next(request)

    def _is_rate_limited(self, api_key: str) -> bool:
        """Check and update rate limit for a given API key."""
        now = time.monotonic()
        window_start = now - self.window_seconds

        if api_key not in self._rate_counters:
            self._rate_counters[api_key] = []

        # Prune old entries
        timestamps = self._rate_counters[api_key]
        self._rate_counters[api_key] = [t for t in timestamps if t > window_start]

        if len(self._rate_counters[api_key]) >= self.rate_limit:
            return True

        self._rate_counters[api_key].append(now)
        return False


async def get_current_app_id(request: Request) -> str:
    """FastAPI dependency to extract authenticated app_id from request."""
    app_id = getattr(request.state, "app_id", None)
    if not app_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return app_id
