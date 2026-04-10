"""Shared OCR endpoint — extract text and structured data from documents.

Supports multiple document types via pluggable parsers.
Domain plugins register their own document parsers (invoice, PAN,
Aadhaar, land record, etc.).

Graceful degradation: if no OCR backend is configured, returns
a helpful error message.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

logger = logging.getLogger(__name__)


class DocumentParser(ABC):
    """Abstract parser for a specific document type."""

    @property
    @abstractmethod
    def document_type(self) -> str:
        """Document type this parser handles (e.g., 'invoice', 'pan_card')."""

    @abstractmethod
    async def parse(self, raw_text: str, image_bytes: bytes | None = None) -> dict[str, Any]:
        """Parse raw OCR text into structured data.

        Returns a dict with extracted fields specific to the document type.
        """


class OCRService:
    """Manages document parsing with pluggable backends."""

    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {}
        self._ocr_backend: Any = None

    def register_parser(self, parser: DocumentParser) -> None:
        """Register a document parser for a specific type."""
        self._parsers[parser.document_type] = parser
        logger.info("OCR parser registered: %s", parser.document_type)

    @property
    def supported_types(self) -> list[str]:
        return list(self._parsers.keys())

    async def extract_text(self, image_bytes: bytes) -> str:
        """Extract raw text from an image using the OCR backend.

        Override or configure this to use PaddleOCR, Tesseract, etc.
        """
        if self._ocr_backend is not None:
            return await self._ocr_backend(image_bytes)

        logger.warning("No OCR backend configured — returning empty text")
        return ""

    async def process_document(
        self,
        image_bytes: bytes,
        document_type: str,
    ) -> dict[str, Any]:
        """Full OCR pipeline: extract text → parse into structured data."""
        parser = self._parsers.get(document_type)
        if parser is None:
            return {
                "error": f"Unsupported document type: {document_type}",
                "supported_types": self.supported_types,
            }

        raw_text = await self.extract_text(image_bytes)
        if not raw_text:
            return {
                "error": "OCR extraction returned no text",
                "document_type": document_type,
            }

        result = await parser.parse(raw_text, image_bytes)
        return {
            "document_type": document_type,
            "raw_text": raw_text,
            "extracted": result,
        }


# Module-level singleton
ocr_service = OCRService()


def create_ocr_router() -> APIRouter:
    """Create the OCR API router."""
    router = APIRouter(prefix="/ocr", tags=["ocr"])

    @router.post("/extract")
    async def extract_document(
        file: UploadFile = File(...),
        document_type: str = Form(default="auto"),
    ) -> dict[str, Any]:
        """Extract structured data from a document image."""
        if not ocr_service.supported_types:
            raise HTTPException(
                503,
                "No document parsers configured. Install a domain plugin that provides OCR support.",
            )

        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(400, "Empty file uploaded")

        max_size = 10 * 1024 * 1024  # 10MB
        if len(image_bytes) > max_size:
            raise HTTPException(413, "File too large. Maximum size is 10MB.")

        result = await ocr_service.process_document(image_bytes, document_type)
        if "error" in result:
            raise HTTPException(400, result["error"])

        return result

    @router.get("/supported-types")
    async def supported_types() -> dict[str, Any]:
        """List supported document types for OCR extraction."""
        return {"supported_types": ocr_service.supported_types}

    return router
