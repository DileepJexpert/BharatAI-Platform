"""Database operations for ASHA Health — visits and workers CRUD."""

import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Visit, Worker

logger = logging.getLogger("asha_db")


class AshaRepository:
    """Async CRUD operations for ASHA Health data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Workers ---

    async def get_or_create_worker(
        self, phone: str, name: str | None = None, district: str | None = None
    ) -> Worker:
        """Get existing worker by phone or create new one."""
        result = await self.session.execute(
            select(Worker).where(Worker.phone == phone)
        )
        worker = result.scalar_one_or_none()

        if worker is None:
            worker = Worker(phone=phone, name=name, district=district)
            self.session.add(worker)
            await self.session.flush()
            logger.info("[ASHA_DB] Created new worker: phone=%s, id=%s", phone, worker.id)
        else:
            logger.info("[ASHA_DB] Found existing worker: phone=%s, id=%s", phone, worker.id)

        return worker

    # --- Visits ---

    async def save_visit(
        self,
        visit_data: dict[str, Any],
        worker_id: uuid.UUID | None = None,
        raw_transcript: str | None = None,
    ) -> Visit:
        """Save a patient visit to the database."""
        visit = Visit(
            worker_id=worker_id,
            patient_name=visit_data.get("patient_name"),
            patient_age=visit_data.get("patient_age"),
            gender=visit_data.get("gender"),
            complaint=visit_data.get("complaint"),
            temperature=visit_data.get("temperature"),
            weight=visit_data.get("weight"),
            visit_date=visit_data.get("visit_date", date.today()),
            referral_needed=visit_data.get("referral_needed", False),
            notes=visit_data.get("notes"),
            raw_transcript=raw_transcript,
            sync_status="pending",
        )
        self.session.add(visit)
        await self.session.flush()
        logger.info("[ASHA_DB] Visit saved: id=%s, patient=%s", visit.id, visit.patient_name)
        return visit

    async def list_visits(
        self,
        worker_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List visits, optionally filtered by worker_id."""
        query = select(Visit).order_by(Visit.created_at.desc()).limit(limit)
        if worker_id:
            query = query.where(Visit.worker_id == worker_id)

        result = await self.session.execute(query)
        visits = result.scalars().all()

        return [
            {
                "id": str(v.id),
                "worker_id": str(v.worker_id) if v.worker_id else None,
                "patient_name": v.patient_name,
                "patient_age": v.patient_age,
                "gender": v.gender,
                "complaint": v.complaint,
                "temperature": float(v.temperature) if v.temperature else None,
                "weight": float(v.weight) if v.weight else None,
                "visit_date": v.visit_date.isoformat() if v.visit_date else None,
                "referral_needed": v.referral_needed,
                "notes": v.notes,
                "sync_status": v.sync_status,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in visits
        ]

    async def check_duplicate(
        self,
        worker_id: uuid.UUID | None,
        patient_name: str | None,
        visit_date: date | None,
    ) -> bool:
        """Check if a visit already exists for this worker+patient+date."""
        if not patient_name or not worker_id:
            return False

        result = await self.session.execute(
            select(func.count(Visit.id)).where(
                Visit.worker_id == worker_id,
                Visit.patient_name == patient_name,
                Visit.visit_date == (visit_date or date.today()),
            )
        )
        count = result.scalar_one()
        return count > 0

    async def get_visit_count(self) -> int:
        """Get total visit count."""
        result = await self.session.execute(select(func.count(Visit.id)))
        return result.scalar_one()
