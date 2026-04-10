"""Tests for core/api/ocr.py — OCR service and document parsing."""

import pytest
from unittest.mock import AsyncMock

from core.api.ocr import DocumentParser, OCRService


class MockInvoiceParser(DocumentParser):
    """Test parser for invoices."""

    @property
    def document_type(self) -> str:
        return "invoice"

    async def parse(self, raw_text: str, image_bytes=None) -> dict:
        return {
            "vendor": "Test Corp",
            "amount": 5000.0,
            "date": "2024-01-15",
        }


class MockPANParser(DocumentParser):
    """Test parser for PAN cards."""

    @property
    def document_type(self) -> str:
        return "pan_card"

    async def parse(self, raw_text: str, image_bytes=None) -> dict:
        return {"pan_number": "ABCDE1234F", "name": "RAMU KUMAR"}


class TestDocumentParser:
    """Test the DocumentParser ABC."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DocumentParser()

    def test_concrete_implementation(self):
        parser = MockInvoiceParser()
        assert parser.document_type == "invoice"


class TestOCRService:
    """Test the OCR service."""

    def test_register_parser(self):
        service = OCRService()
        service.register_parser(MockInvoiceParser())
        assert "invoice" in service.supported_types

    def test_register_multiple_parsers(self):
        service = OCRService()
        service.register_parser(MockInvoiceParser())
        service.register_parser(MockPANParser())
        assert len(service.supported_types) == 2
        assert "invoice" in service.supported_types
        assert "pan_card" in service.supported_types

    @pytest.mark.asyncio
    async def test_extract_text_no_backend(self):
        service = OCRService()
        text = await service.extract_text(b"fake image bytes")
        assert text == ""

    @pytest.mark.asyncio
    async def test_extract_text_with_backend(self):
        service = OCRService()
        service._ocr_backend = AsyncMock(return_value="Invoice #123\nTotal: Rs 5000")
        text = await service.extract_text(b"fake image")
        assert "Invoice #123" in text

    @pytest.mark.asyncio
    async def test_process_document_success(self):
        service = OCRService()
        service.register_parser(MockInvoiceParser())
        service._ocr_backend = AsyncMock(return_value="Invoice #123\nTotal: Rs 5000")

        result = await service.process_document(b"fake image", "invoice")
        assert result["document_type"] == "invoice"
        assert result["extracted"]["vendor"] == "Test Corp"
        assert result["extracted"]["amount"] == 5000.0

    @pytest.mark.asyncio
    async def test_process_document_unsupported_type(self):
        service = OCRService()
        result = await service.process_document(b"fake image", "unknown_type")
        assert "error" in result
        assert "Unsupported" in result["error"]

    @pytest.mark.asyncio
    async def test_process_document_no_text_extracted(self):
        service = OCRService()
        service.register_parser(MockInvoiceParser())
        # No OCR backend configured — returns empty text

        result = await service.process_document(b"fake image", "invoice")
        assert "error" in result
        assert "no text" in result["error"]

    def test_supported_types_empty(self):
        service = OCRService()
        assert service.supported_types == []
