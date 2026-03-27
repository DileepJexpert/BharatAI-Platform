"""SQLAlchemy models for ASHA Health — workers and visits tables.

All tables live in the 'asha_health' PostgreSQL schema.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base

SCHEMA = "asha_health"


class Worker(Base):
    """ASHA worker who records patient visits."""

    __tablename__ = "workers"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(10), default="hi")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    visits: Mapped[list["Visit"]] = relationship(back_populates="worker")


class Visit(Base):
    """Patient visit recorded by an ASHA worker."""

    __tablename__ = "visits"
    __table_args__ = (
        Index("ix_visits_worker_date", "worker_id", "visit_date", _schema=SCHEMA),
        Index("ix_visits_sync_status", "sync_status", _schema=SCHEMA),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.workers.id"),
    )
    patient_name: Mapped[str | None] = mapped_column(String(100))
    patient_age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(10))
    complaint: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[float | None] = mapped_column(Numeric(4, 1))
    weight: Mapped[float | None] = mapped_column(Numeric(5, 2))
    visit_date: Mapped[date] = mapped_column(Date, default=date.today)
    referral_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    raw_transcript: Mapped[str | None] = mapped_column(Text)
    sync_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    worker: Mapped[Worker | None] = relationship(back_populates="visits")
