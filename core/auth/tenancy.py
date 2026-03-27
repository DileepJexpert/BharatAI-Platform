"""App tenancy helpers — schema isolation per app_id."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Known app_id -> PostgreSQL schema mapping
APP_SCHEMAS: dict[str, str] = {
    "asha_health": "asha_health",
    "lawyer_ai": "lawyer_ai",
    "agri_dealer": "agri_dealer",
    "mfi_agent": "mfi_agent",
    "job_match": "job_match",
    "teacher_ai": "teacher_ai",
}


class TenancyViolationError(Exception):
    """Raised when an app tries to access another app's schema."""
    pass


def get_schema_for_app(app_id: str) -> str:
    """Return the PostgreSQL schema name for the given app_id.

    Raises:
        ValueError: if app_id is not registered.
    """
    schema = APP_SCHEMAS.get(app_id)
    if schema is None:
        raise ValueError(f"Unknown app_id: '{app_id}'. Registered apps: {list(APP_SCHEMAS.keys())}")
    return schema


def validate_access(requesting_app_id: str, target_schema: str) -> None:
    """Ensure an app only accesses its own schema.

    Raises:
        TenancyViolationError: if cross-app access is attempted.
    """
    allowed_schema = get_schema_for_app(requesting_app_id)
    if allowed_schema != target_schema:
        raise TenancyViolationError(
            f"App '{requesting_app_id}' (schema '{allowed_schema}') "
            f"cannot access schema '{target_schema}'"
        )
