"""Notification engine — domain-agnostic push notifications.

Supports multiple channels: SMS, WhatsApp, push notification.
Domain plugins register notification handlers; the engine routes
and retries delivery with configurable backoff.

Graceful degradation: if no delivery backend is configured,
notifications are logged but not sent.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Notification:
    """A notification to be delivered."""

    recipient: str  # phone number or device token
    channel: NotificationChannel
    title: str
    body: str
    app_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    attempts: int = 0
    max_retries: int = 3
    notification_id: str = ""
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()
        if not self.notification_id:
            import uuid
            self.notification_id = str(uuid.uuid4())


class NotificationBackend(ABC):
    """Abstract backend for delivering notifications via a specific channel."""

    @property
    @abstractmethod
    def channel(self) -> NotificationChannel:
        """Which channel this backend handles."""

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Attempt to deliver a notification. Returns True on success."""


class NotificationEngine:
    """Routes notifications to registered backends with retry logic."""

    def __init__(self) -> None:
        self._backends: dict[NotificationChannel, NotificationBackend] = {}
        self._queue: list[Notification] = []

    def register_backend(self, backend: NotificationBackend) -> None:
        """Register a delivery backend for a channel."""
        self._backends[backend.channel] = backend
        logger.info("Notification backend registered: %s", backend.channel.value)

    @property
    def available_channels(self) -> list[str]:
        return [ch.value for ch in self._backends]

    async def send(self, notification: Notification) -> Notification:
        """Send a notification immediately via its channel backend.

        Returns the notification with updated status.
        """
        backend = self._backends.get(notification.channel)
        if backend is None:
            logger.warning(
                "No backend for channel %s — notification %s logged only",
                notification.channel.value,
                notification.notification_id,
            )
            notification.status = NotificationStatus.FAILED
            return notification

        notification.attempts += 1
        try:
            success = await backend.send(notification)
            if success:
                notification.status = NotificationStatus.SENT
                logger.info(
                    "Notification %s sent via %s to %s",
                    notification.notification_id,
                    notification.channel.value,
                    notification.recipient,
                )
            else:
                if notification.attempts < notification.max_retries:
                    notification.status = NotificationStatus.RETRYING
                    self._queue.append(notification)
                else:
                    notification.status = NotificationStatus.FAILED
                    logger.warning(
                        "Notification %s failed after %d attempts",
                        notification.notification_id,
                        notification.attempts,
                    )
        except Exception as exc:
            logger.error(
                "Notification %s delivery error: %s",
                notification.notification_id,
                exc,
            )
            if notification.attempts < notification.max_retries:
                notification.status = NotificationStatus.RETRYING
                self._queue.append(notification)
            else:
                notification.status = NotificationStatus.FAILED

        return notification

    async def process_retry_queue(self) -> int:
        """Process pending retries. Returns number of notifications retried."""
        if not self._queue:
            return 0

        to_retry = self._queue[:]
        self._queue.clear()
        count = 0

        for notification in to_retry:
            await self.send(notification)
            count += 1

        return count

    @property
    def pending_count(self) -> int:
        return len(self._queue)
