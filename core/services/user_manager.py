"""User management — phone+OTP authentication and user profiles.

Provides domain-agnostic user identity shared across all apps.
Each app plugin can extend the user profile with domain-specific fields
via the metadata dict.

Auth flow: phone → generate OTP → verify OTP → JWT token
Graceful degradation: works without PostgreSQL (in-memory store for dev).
"""

import hashlib
import hmac
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Optional JWT support
try:
    import jwt as pyjwt

    JWT_AVAILABLE = True
except BaseException:
    pyjwt = None  # type: ignore[assignment]
    JWT_AVAILABLE = False
    logger.info("pyjwt not available — JWT auth will be unavailable")


JWT_SECRET = os.getenv("JWT_SECRET", "bharatai-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
OTP_LENGTH = int(os.getenv("OTP_LENGTH", "6"))
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))


@dataclass
class UserProfile:
    """Core user identity shared across all domain apps."""

    user_id: str
    phone: str
    name: str = ""
    language: str = "hi"
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class OTPRecord:
    """Temporary OTP storage."""

    phone: str
    code: str
    created_at: float
    expires_at: float
    verified: bool = False


class UserManager:
    """Manages user registration, OTP auth, and profile storage.

    Uses in-memory storage by default. Domain plugins can override
    with database-backed implementations.
    """

    def __init__(self) -> None:
        self._users: dict[str, UserProfile] = {}  # user_id -> profile
        self._phone_index: dict[str, str] = {}  # phone -> user_id
        self._otps: dict[str, OTPRecord] = {}  # phone -> OTP record

    def generate_otp(self, phone: str) -> str:
        """Generate and store a new OTP for a phone number."""
        code = "".join(str(random.randint(0, 9)) for _ in range(OTP_LENGTH))
        now = time.time()
        self._otps[phone] = OTPRecord(
            phone=phone,
            code=code,
            created_at=now,
            expires_at=now + OTP_EXPIRY_SECONDS,
        )
        logger.info("OTP generated for %s (expires in %ds)", phone, OTP_EXPIRY_SECONDS)
        return code

    def verify_otp(self, phone: str, code: str) -> bool:
        """Verify an OTP code. Returns True if valid and not expired."""
        record = self._otps.get(phone)
        if record is None:
            return False
        if record.verified:
            return False
        if time.time() > record.expires_at:
            del self._otps[phone]
            return False
        if not hmac.compare_digest(record.code, code):
            return False

        record.verified = True
        del self._otps[phone]
        return True

    def get_or_create_user(self, phone: str, name: str = "") -> UserProfile:
        """Find an existing user by phone or create a new one."""
        existing_id = self._phone_index.get(phone)
        if existing_id and existing_id in self._users:
            return self._users[existing_id]

        user_id = hashlib.sha256(phone.encode()).hexdigest()[:16]
        profile = UserProfile(user_id=user_id, phone=phone, name=name)
        self._users[user_id] = profile
        self._phone_index[phone] = user_id
        logger.info("User created: %s (phone=%s)", user_id, phone)
        return profile

    def get_user(self, user_id: str) -> UserProfile | None:
        """Get a user profile by ID."""
        return self._users.get(user_id)

    def get_user_by_phone(self, phone: str) -> UserProfile | None:
        """Get a user profile by phone number."""
        uid = self._phone_index.get(phone)
        if uid:
            return self._users.get(uid)
        return None

    def update_profile(self, user_id: str, **kwargs: Any) -> UserProfile | None:
        """Update user profile fields. Metadata is merged, not replaced."""
        profile = self._users.get(user_id)
        if profile is None:
            return None

        for key, value in kwargs.items():
            if key == "metadata" and isinstance(value, dict):
                profile.metadata.update(value)
            elif hasattr(profile, key):
                setattr(profile, key, value)

        return profile

    def create_token(self, user_id: str) -> str | None:
        """Create a JWT token for authenticated user."""
        if not JWT_AVAILABLE:
            logger.warning("pyjwt not installed — cannot create JWT token")
            return None

        profile = self._users.get(user_id)
        if profile is None:
            return None

        payload = {
            "sub": user_id,
            "phone": profile.phone,
            "iat": int(time.time()),
            "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
        }
        return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify a JWT token. Returns the payload if valid, None otherwise."""
        if not JWT_AVAILABLE:
            return None

        try:
            payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except Exception:
            return None

    @property
    def user_count(self) -> int:
        return len(self._users)
