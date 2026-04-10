"""Tests for core/services/user_manager.py — user management + OTP + JWT."""

import time
import pytest
from unittest.mock import patch

from core.services.user_manager import UserManager, UserProfile, OTP_EXPIRY_SECONDS


class TestUserProfile:
    """Test the UserProfile dataclass."""

    def test_create_profile(self):
        profile = UserProfile(user_id="u1", phone="+919876543210")
        assert profile.user_id == "u1"
        assert profile.phone == "+919876543210"
        assert profile.name == ""
        assert profile.language == "hi"
        assert profile.created_at > 0
        assert profile.metadata == {}

    def test_profile_with_metadata(self):
        profile = UserProfile(
            user_id="u1",
            phone="+91123",
            name="Ramu",
            metadata={"district": "Indore"},
        )
        assert profile.name == "Ramu"
        assert profile.metadata["district"] == "Indore"


class TestOTPFlow:
    """Test OTP generation and verification."""

    def test_generate_otp(self):
        mgr = UserManager()
        code = mgr.generate_otp("+919876543210")
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_otp_success(self):
        mgr = UserManager()
        code = mgr.generate_otp("+91123")
        assert mgr.verify_otp("+91123", code) is True

    def test_verify_otp_wrong_code(self):
        mgr = UserManager()
        mgr.generate_otp("+91123")
        assert mgr.verify_otp("+91123", "000000") is False

    def test_verify_otp_no_record(self):
        mgr = UserManager()
        assert mgr.verify_otp("+91123", "123456") is False

    def test_verify_otp_already_used(self):
        mgr = UserManager()
        code = mgr.generate_otp("+91123")
        assert mgr.verify_otp("+91123", code) is True
        # Second verification should fail
        assert mgr.verify_otp("+91123", code) is False

    def test_verify_otp_expired(self):
        mgr = UserManager()
        code = mgr.generate_otp("+91123")
        # Manually expire the OTP
        mgr._otps["+91123"].expires_at = time.time() - 1
        assert mgr.verify_otp("+91123", code) is False

    def test_generate_otp_replaces_previous(self):
        mgr = UserManager()
        code1 = mgr.generate_otp("+91123")
        code2 = mgr.generate_otp("+91123")
        # Old code should not work
        if code1 != code2:
            assert mgr.verify_otp("+91123", code1) is False


class TestUserManagement:
    """Test user CRUD operations."""

    def test_create_user(self):
        mgr = UserManager()
        profile = mgr.get_or_create_user("+919876543210", "Ramu")
        assert profile.phone == "+919876543210"
        assert profile.name == "Ramu"
        assert profile.user_id  # Auto-generated

    def test_get_existing_user(self):
        mgr = UserManager()
        p1 = mgr.get_or_create_user("+91123", "User1")
        p2 = mgr.get_or_create_user("+91123", "User1Again")
        assert p1.user_id == p2.user_id  # Same user returned

    def test_get_user_by_id(self):
        mgr = UserManager()
        created = mgr.get_or_create_user("+91123", "Test")
        found = mgr.get_user(created.user_id)
        assert found is not None
        assert found.phone == "+91123"

    def test_get_user_by_id_not_found(self):
        mgr = UserManager()
        assert mgr.get_user("nonexistent") is None

    def test_get_user_by_phone(self):
        mgr = UserManager()
        mgr.get_or_create_user("+91123", "Test")
        found = mgr.get_user_by_phone("+91123")
        assert found is not None
        assert found.name == "Test"

    def test_get_user_by_phone_not_found(self):
        mgr = UserManager()
        assert mgr.get_user_by_phone("+91999") is None

    def test_update_profile(self):
        mgr = UserManager()
        profile = mgr.get_or_create_user("+91123")
        updated = mgr.update_profile(profile.user_id, name="Updated", language="en")
        assert updated is not None
        assert updated.name == "Updated"
        assert updated.language == "en"

    def test_update_profile_metadata_merge(self):
        mgr = UserManager()
        profile = mgr.get_or_create_user("+91123")
        mgr.update_profile(profile.user_id, metadata={"district": "Indore"})
        mgr.update_profile(profile.user_id, metadata={"crop": "wheat"})
        # Both fields should be present
        assert profile.metadata["district"] == "Indore"
        assert profile.metadata["crop"] == "wheat"

    def test_update_profile_not_found(self):
        mgr = UserManager()
        assert mgr.update_profile("nonexistent", name="X") is None

    def test_user_count(self):
        mgr = UserManager()
        assert mgr.user_count == 0
        mgr.get_or_create_user("+91001")
        mgr.get_or_create_user("+91002")
        assert mgr.user_count == 2


class TestJWT:
    """Test JWT token creation and verification."""

    def test_create_token(self):
        mgr = UserManager()
        profile = mgr.get_or_create_user("+91123", "Test")
        token = mgr.create_token(profile.user_id)
        # Token depends on pyjwt availability
        if token is not None:
            assert isinstance(token, str)
            assert len(token) > 0

    def test_create_token_unknown_user(self):
        mgr = UserManager()
        token = mgr.create_token("nonexistent")
        assert token is None

    def test_verify_token_roundtrip(self):
        mgr = UserManager()
        profile = mgr.get_or_create_user("+91123", "Test")
        token = mgr.create_token(profile.user_id)
        if token is not None:
            payload = mgr.verify_token(token)
            assert payload is not None
            assert payload["sub"] == profile.user_id
            assert payload["phone"] == "+91123"

    def test_verify_invalid_token(self):
        mgr = UserManager()
        result = mgr.verify_token("invalid.token.here")
        assert result is None
