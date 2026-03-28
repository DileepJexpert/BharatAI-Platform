"""Database operations for Lawyer AI — queries CRUD."""

import logging
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Query

logger = logging.getLogger("lawyer_db")


class LawyerRepository:
    """Async CRUD operations for Lawyer AI data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_query(
        self,
        user_id: str | None,
        query_text: str,
        response_text: str | None = None,
        sections_cited: list[str] | None = None,
        severity: str | None = None,
        language: str = "hi",
    ) -> Query:
        """Save a legal query to the database."""
        import json
        query = Query(
            user_id=user_id,
            query_text=query_text,
            response_text=response_text,
            sections_cited=json.dumps(sections_cited) if sections_cited else None,
            severity=severity,
            language=language,
        )
        self.session.add(query)
        await self.session.flush()
        logger.info("[LAWYER_DB] Query saved: id=%s", query.id)
        return query

    async def list_queries(
        self, user_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List queries, optionally filtered by user_id."""
        import json
        stmt = select(Query).order_by(Query.created_at.desc()).limit(limit)
        if user_id:
            stmt = stmt.where(Query.user_id == user_id)

        result = await self.session.execute(stmt)
        queries = result.scalars().all()

        return [
            {
                "id": str(q.id),
                "user_id": q.user_id,
                "query_text": q.query_text,
                "response_text": q.response_text,
                "sections_cited": json.loads(q.sections_cited) if q.sections_cited else None,
                "severity": q.severity,
                "language": q.language,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q in queries
        ]
