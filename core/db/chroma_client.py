"""ChromaDB RAG client — domain-aware vector search.

Each domain plugin gets its own collection namespace to prevent data leakage.
Collection naming: "{app_id}_{collection}" (e.g., "kisanmitra_schemes").

Graceful degradation: if ChromaDB is not available, operations log warnings
and return empty results, matching the platform's pattern for PostgreSQL/Redis.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Optional: only import chromadb if available
try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.info("chromadb not installed — RAG search will be unavailable")


class ChromaClient:
    """Shared ChromaDB client with domain-isolated collections."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self._host = host or os.getenv("CHROMA_HOST", "localhost")
        self._port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self._client: Any | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        """Initialize the ChromaDB HTTP client."""
        if not CHROMADB_AVAILABLE:
            logger.warning("chromadb package not installed, skipping connection")
            return

        try:
            logger.info("Connecting to ChromaDB at %s:%d", self._host, self._port)
            self._client = chromadb.HttpClient(host=self._host, port=self._port)
            # Test connection by listing collections
            self._client.list_collections()
            self._connected = True
            logger.info("ChromaDB connected")
        except Exception as exc:
            logger.warning("ChromaDB connection failed: %s", exc)
            self._client = None
            self._connected = False

    def _collection_name(self, app_id: str, collection: str) -> str:
        """Build domain-isolated collection name."""
        return f"{app_id}_{collection}"

    def get_or_create_collection(
        self, app_id: str, collection: str
    ) -> Any | None:
        """Return an existing collection or create a new one."""
        if not self._connected or self._client is None:
            logger.debug("ChromaDB not connected, cannot get collection")
            return None
        name = self._collection_name(app_id, collection)
        return self._client.get_or_create_collection(name=name)

    def add_documents(
        self,
        app_id: str,
        collection: str,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """Add documents to a domain-specific collection."""
        coll = self.get_or_create_collection(app_id, collection)
        if coll is None:
            logger.warning("Cannot add documents — ChromaDB not available")
            return

        if ids is None:
            name = self._collection_name(app_id, collection)
            ids = [f"{name}_{i}" for i in range(len(documents))]

        kwargs: dict[str, Any] = {"documents": documents, "ids": ids}
        if metadatas:
            kwargs["metadatas"] = metadatas

        coll.add(**kwargs)
        logger.info(
            "Added %d documents to %s/%s",
            len(documents),
            app_id,
            collection,
        )

    def search(
        self,
        app_id: str,
        collection: str,
        query: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across a domain collection.

        Returns list of result dicts with 'document', 'metadata', 'distance'.
        """
        coll = self.get_or_create_collection(app_id, collection)
        if coll is None:
            return []

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        try:
            results = coll.query(**kwargs)
            # Flatten chromadb's nested result format
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            return [
                {
                    "document": doc,
                    "metadata": meta,
                    "distance": dist,
                }
                for doc, meta, dist in zip(docs, metas, distances)
            ]
        except Exception as exc:
            logger.warning("ChromaDB search failed: %s", exc)
            return []

    def delete_collection(self, app_id: str, collection: str) -> None:
        """Delete a domain collection."""
        if not self._connected or self._client is None:
            return
        name = self._collection_name(app_id, collection)
        try:
            self._client.delete_collection(name)
            logger.info("Deleted collection: %s", name)
        except Exception as exc:
            logger.warning("Failed to delete collection %s: %s", name, exc)
