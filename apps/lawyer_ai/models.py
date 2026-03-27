"""SQLAlchemy models for Lawyer AI — queries table.

All tables live in the 'lawyer_ai' PostgreSQL schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base

SCHEMA = "lawyer_ai"


class Query(Base):
    """Legal query recorded by a user."""

    __tablename__ = "queries"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str | None] = mapped_column(String(100))
    query_text: Mapped[str | None] = mapped_column(Text)
    response_text: Mapped[str | None] = mapped_column(Text)
    sections_cited: Mapped[str | None] = mapped_column(Text)  # JSON string
    severity: Mapped[str | None] = mapped_column(String(10))
    language: Mapped[str] = mapped_column(String(10), default="hi")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
