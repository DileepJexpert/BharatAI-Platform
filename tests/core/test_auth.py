"""Tests for core/auth/ — AUTH-001 through AUTH-005."""

import os
import pytest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth.middleware import AuthMiddleware
from core.auth.tenancy import (
    get_schema_for_app,
    validate_access,
    TenancyViolationError,
)


# --- Test app fixture ---

def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with auth middleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware, rate_limit=100, window_seconds=60)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/asha_health/test")
    async def asha_test():
        return {"app": "asha_health"}

    @app.get("/lawyer_ai/test")
    async def lawyer_test():
        return {"app": "lawyer_ai"}

    return app


@pytest.fixture
def env_keys():
    """Set up API keys in environment."""
    with patch.dict(os.environ, {
        "ASHA_HEALTH_API_KEY": "dev-asha-key-001",
        "LAWYER_AI_API_KEY": "dev-lawyer-key-001",
    }):
        yield


@pytest.fixture
def test_client(env_keys):
    """Create a test client with auth middleware."""
    app = _create_test_app()
    return TestClient(app)


# --- Auth Tests ---

class TestAUTH001ValidKey:
    """AUTH-001: Valid API key — request proceeds."""

    def test_valid_key_succeeds(self, test_client):
        response = test_client.get(
            "/asha_health/test",
            headers={"X-API-Key": "dev-asha-key-001"},
        )
        assert response.status_code == 200
        assert response.json()["app"] == "asha_health"


class TestAUTH002MissingKey:
    """AUTH-002: Missing API key — returns 401."""

    def test_missing_key(self, test_client):
        response = test_client.get("/asha_health/test")
        assert response.status_code == 401
        assert "Missing" in response.json()["detail"]


class TestAUTH003CrossAppAccess:
    """AUTH-003: Cross-app data access — returns 403."""

    def test_cross_app_forbidden(self, test_client):
        # lawyer_ai key trying to access asha_health route
        response = test_client.get(
            "/asha_health/test",
            headers={"X-API-Key": "dev-lawyer-key-001"},
        )
        assert response.status_code == 403
        assert "cannot access" in response.json()["detail"]


class TestAUTH004RateLimit:
    """AUTH-004: Rate limiting — 101st request returns 429."""

    def test_rate_limit_exceeded(self, env_keys):
        # Create app with low rate limit for testing
        app = FastAPI()
        app.add_middleware(AuthMiddleware, rate_limit=5, window_seconds=60)

        @app.get("/asha_health/test")
        async def asha_test():
            return {"ok": True}

        client = TestClient(app)
        headers = {"X-API-Key": "dev-asha-key-001"}

        # First 5 should succeed
        for i in range(5):
            resp = client.get("/asha_health/test", headers=headers)
            assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

        # 6th should be rate limited
        resp = client.get("/asha_health/test", headers=headers)
        assert resp.status_code == 429
        assert "Rate limit" in resp.json()["detail"]


class TestAUTH005InvalidKey:
    """AUTH-005: Invalid/expired key — returns 401."""

    def test_invalid_key(self, test_client):
        response = test_client.get(
            "/asha_health/test",
            headers={"X-API-Key": "wrong-key-12345"},
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]


class TestPublicRoutes:
    """Public routes should work without auth."""

    def test_health_no_auth(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200


# --- Tenancy Tests ---

class TestTenancy:
    def test_get_schema_for_known_app(self):
        assert get_schema_for_app("asha_health") == "asha_health"
        assert get_schema_for_app("lawyer_ai") == "lawyer_ai"

    def test_get_schema_unknown_app(self):
        with pytest.raises(ValueError, match="Unknown app_id"):
            get_schema_for_app("nonexistent")

    def test_validate_same_app_access(self):
        validate_access("asha_health", "asha_health")  # Should not raise

    def test_validate_cross_app_access(self):
        with pytest.raises(TenancyViolationError, match="cannot access"):
            validate_access("lawyer_ai", "asha_health")
