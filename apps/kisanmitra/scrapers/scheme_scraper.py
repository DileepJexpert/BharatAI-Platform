"""Government scheme scraper — loads scheme data into ChromaDB for RAG search.

Extends core/scraper/base.py BaseScraper. Runs daily.
In MVP, loads from the built-in SAMPLE_SCHEMES data.
In production, would scrape myscheme.gov.in or use API.
"""

import logging
from typing import Any

from core.scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class SchemeScraper(BaseScraper):
    """Loads government scheme data into ChromaDB for RAG search."""

    @property
    def scraper_id(self) -> str:
        return "scheme_data"

    @property
    def schedule_hours(self) -> float:
        return 24.0  # Daily

    async def scrape(self) -> dict:
        """Load scheme data into ChromaDB collection.

        In production, this would scrape myscheme.gov.in.
        For MVP, loads from built-in sample data.
        """
        from apps.kisanmitra.tools.scheme_tools import SAMPLE_SCHEMES

        # Try to add to ChromaDB
        try:
            from core.db.chroma_client import ChromaClient
            client = ChromaClient()
            if not client.is_connected:
                logger.info("ChromaDB not connected — scheme data in memory only")
                return {"records_added": len(SAMPLE_SCHEMES), "errors": [], "target": "memory"}

            documents = []
            metadatas = []
            ids = []

            for scheme in SAMPLE_SCHEMES:
                text = (
                    f"{scheme['name_en']} ({scheme.get('name_hi', '')}). "
                    f"{scheme['description']} "
                    f"Sector: {scheme.get('sector', 'general')}. "
                    f"Eligibility: {scheme.get('eligibility', '')}."
                )
                documents.append(text)
                metadatas.append({
                    "scheme_code": scheme["scheme_code"],
                    "sector": scheme.get("sector", "general"),
                    "benefit_type": scheme.get("benefit_type", ""),
                })
                ids.append(f"scheme_{scheme['scheme_code']}")

            client.add_documents(
                app_id="kisanmitra",
                collection="schemes",
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

            logger.info("Loaded %d schemes into ChromaDB", len(documents))
            return {"records_added": len(documents), "errors": [], "target": "chromadb"}

        except Exception as exc:
            logger.warning("Scheme ChromaDB load failed: %s", exc)
            return {"records_added": len(SAMPLE_SCHEMES), "errors": [str(exc)], "target": "memory"}
