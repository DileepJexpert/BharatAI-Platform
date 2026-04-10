"""Tests for core/services/notification.py — notification engine."""

import pytest
from unittest.mock import AsyncMock

from core.services.notification import (
    Notification,
    NotificationBackend,
    NotificationChannel,
    NotificationEngine,
    NotificationStatus,
)


class MockSMSBackend(NotificationBackend):
    """Test SMS backend that always succeeds."""

    def __init__(self, should_succeed: bool = True):
        self._should_succeed = should_succeed
        self.sent: list[Notification] = []

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.SMS

    async def send(self, notification: Notification) -> bool:
        self.sent.append(notification)
        return self._should_succeed


class MockWhatsAppBackend(NotificationBackend):
    """Test WhatsApp backend."""

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.WHATSAPP

    async def send(self, notification: Notification) -> bool:
        return True


class FailingBackend(NotificationBackend):
    """Backend that raises an exception."""

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.PUSH

    async def send(self, notification: Notification) -> bool:
        raise ConnectionError("Push service down")


class TestNotification:
    """Test the Notification dataclass."""

    def test_create_notification(self):
        n = Notification(
            recipient="+919876543210",
            channel=NotificationChannel.SMS,
            title="Price Alert",
            body="Wheat price crossed Rs 2500",
            app_id="kisanmitra",
        )
        assert n.recipient == "+919876543210"
        assert n.status == NotificationStatus.PENDING
        assert n.attempts == 0
        assert n.notification_id  # Auto-generated
        assert n.created_at > 0

    def test_notification_metadata(self):
        n = Notification(
            recipient="+91123",
            channel=NotificationChannel.WHATSAPP,
            title="Test",
            body="Body",
            app_id="test",
            metadata={"crop": "wheat"},
        )
        assert n.metadata["crop"] == "wheat"


class TestNotificationEngine:
    """Test the notification routing engine."""

    def test_register_backend(self):
        engine = NotificationEngine()
        engine.register_backend(MockSMSBackend())
        assert "sms" in engine.available_channels

    def test_register_multiple_backends(self):
        engine = NotificationEngine()
        engine.register_backend(MockSMSBackend())
        engine.register_backend(MockWhatsAppBackend())
        assert len(engine.available_channels) == 2

    @pytest.mark.asyncio
    async def test_send_success(self):
        engine = NotificationEngine()
        backend = MockSMSBackend()
        engine.register_backend(backend)

        n = Notification(
            recipient="+91123",
            channel=NotificationChannel.SMS,
            title="Test",
            body="Hello",
            app_id="test",
        )
        result = await engine.send(n)
        assert result.status == NotificationStatus.SENT
        assert result.attempts == 1
        assert len(backend.sent) == 1

    @pytest.mark.asyncio
    async def test_send_no_backend(self):
        engine = NotificationEngine()
        n = Notification(
            recipient="+91123",
            channel=NotificationChannel.SMS,
            title="Test",
            body="Hello",
            app_id="test",
        )
        result = await engine.send(n)
        assert result.status == NotificationStatus.FAILED

    @pytest.mark.asyncio
    async def test_send_failure_queues_retry(self):
        engine = NotificationEngine()
        engine.register_backend(MockSMSBackend(should_succeed=False))

        n = Notification(
            recipient="+91123",
            channel=NotificationChannel.SMS,
            title="Test",
            body="Hello",
            app_id="test",
            max_retries=3,
        )
        result = await engine.send(n)
        assert result.status == NotificationStatus.RETRYING
        assert engine.pending_count == 1

    @pytest.mark.asyncio
    async def test_send_failure_max_retries_exhausted(self):
        engine = NotificationEngine()
        engine.register_backend(MockSMSBackend(should_succeed=False))

        n = Notification(
            recipient="+91123",
            channel=NotificationChannel.SMS,
            title="Test",
            body="Hello",
            app_id="test",
            max_retries=1,
        )
        # First attempt
        result = await engine.send(n)
        assert result.status == NotificationStatus.FAILED

    @pytest.mark.asyncio
    async def test_send_exception_queues_retry(self):
        engine = NotificationEngine()
        engine.register_backend(FailingBackend())

        n = Notification(
            recipient="device-token",
            channel=NotificationChannel.PUSH,
            title="Test",
            body="Hello",
            app_id="test",
            max_retries=3,
        )
        result = await engine.send(n)
        assert result.status == NotificationStatus.RETRYING
        assert engine.pending_count == 1

    @pytest.mark.asyncio
    async def test_process_retry_queue(self):
        engine = NotificationEngine()
        backend = MockSMSBackend(should_succeed=False)
        engine.register_backend(backend)

        n = Notification(
            recipient="+91123",
            channel=NotificationChannel.SMS,
            title="Test",
            body="Hello",
            app_id="test",
            max_retries=3,
        )
        await engine.send(n)
        assert engine.pending_count == 1

        count = await engine.process_retry_queue()
        assert count == 1

    @pytest.mark.asyncio
    async def test_process_empty_retry_queue(self):
        engine = NotificationEngine()
        count = await engine.process_retry_queue()
        assert count == 0
