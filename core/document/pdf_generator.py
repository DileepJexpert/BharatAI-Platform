"""PDF document generator — shared report/invoice generation.

Domain plugins use this to generate PDFs for invoices, reports,
certificates, and other documents. Uses fpdf2 for PDF creation.

Graceful degradation: if fpdf2 is not installed, returns None
and logs a warning.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Optional: only import fpdf if available
try:
    from fpdf import FPDF

    FPDF_AVAILABLE = True
except BaseException:
    FPDF_AVAILABLE = False
    FPDF = None  # type: ignore[assignment,misc]
    logger.info("fpdf2 not available — PDF generation will be unavailable")


@dataclass
class TableColumn:
    """Column definition for PDF tables."""

    header: str
    width: float
    align: str = "L"


@dataclass
class PDFConfig:
    """Configuration for PDF generation."""

    title: str = "BharatAI Document"
    author: str = "BharatAI Platform"
    orientation: str = "P"  # P=portrait, L=landscape
    page_size: str = "A4"
    margin: float = 10.0
    font_family: str = "Helvetica"
    font_size: int = 10
    header_text: str = ""
    footer_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PDFGenerator:
    """Generates PDF documents with tables, text sections, and headers."""

    def __init__(self, config: PDFConfig | None = None) -> None:
        self._config = config or PDFConfig()

    def generate_report(
        self,
        sections: list[dict[str, Any]],
        output_path: str,
    ) -> str | None:
        """Generate a PDF report with multiple sections.

        Each section dict can have:
            - "heading": str — section title
            - "text": str — body text
            - "table": {"columns": list[TableColumn], "rows": list[list[str]]}
            - "key_value": list[tuple[str, str]] — key-value pairs

        Returns the output file path on success, None on failure.
        """
        if not FPDF_AVAILABLE:
            logger.warning("fpdf2 not installed — cannot generate PDF")
            return None

        try:
            pdf = FPDF(
                orientation=self._config.orientation,
                format=self._config.page_size,
            )
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_margins(
                self._config.margin,
                self._config.margin,
                self._config.margin,
            )
            pdf.set_title(self._config.title)
            pdf.set_author(self._config.author)

            pdf.add_page()

            # Document title
            pdf.set_font(self._config.font_family, "B", 16)
            pdf.cell(0, 12, self._config.title, new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(4)

            # Header text
            if self._config.header_text:
                pdf.set_font(self._config.font_family, "I", 9)
                pdf.cell(
                    0, 6, self._config.header_text,
                    new_x="LMARGIN", new_y="NEXT", align="C",
                )
                pdf.ln(4)

            # Render each section
            for section in sections:
                self._render_section(pdf, section)

            # Footer
            if self._config.footer_text:
                pdf.set_y(-25)
                pdf.set_font(self._config.font_family, "I", 8)
                pdf.cell(
                    0, 6, self._config.footer_text,
                    new_x="LMARGIN", new_y="NEXT", align="C",
                )

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            pdf.output(output_path)
            logger.info("PDF generated: %s", output_path)
            return output_path

        except Exception as exc:
            logger.error("PDF generation failed: %s", exc)
            return None

    def _render_section(self, pdf: Any, section: dict[str, Any]) -> None:
        """Render a single section into the PDF."""
        # Section heading
        heading = section.get("heading")
        if heading:
            pdf.set_font(self._config.font_family, "B", 12)
            pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # Body text
        text = section.get("text")
        if text:
            pdf.set_font(self._config.font_family, "", self._config.font_size)
            pdf.multi_cell(0, 5, text)
            pdf.ln(3)

        # Key-value pairs
        kv_pairs = section.get("key_value")
        if kv_pairs:
            pdf.set_font(self._config.font_family, "", self._config.font_size)
            for key, value in kv_pairs:
                pdf.set_font(self._config.font_family, "B", self._config.font_size)
                pdf.cell(60, 6, f"{key}:")
                pdf.set_font(self._config.font_family, "", self._config.font_size)
                pdf.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

        # Table
        table_data = section.get("table")
        if table_data:
            self._render_table(pdf, table_data)

    def _render_table(self, pdf: Any, table_data: dict[str, Any]) -> None:
        """Render a table into the PDF."""
        columns = table_data.get("columns", [])
        rows = table_data.get("rows", [])

        if not columns or not rows:
            return

        # Header row
        pdf.set_font(self._config.font_family, "B", self._config.font_size)
        for col in columns:
            width = col.get("width", 40) if isinstance(col, dict) else 40
            header = col.get("header", "") if isinstance(col, dict) else str(col)
            align = col.get("align", "L") if isinstance(col, dict) else "L"
            pdf.cell(width, 7, header, border=1, align=align)
        pdf.ln()

        # Data rows
        pdf.set_font(self._config.font_family, "", self._config.font_size)
        for row in rows:
            for i, cell_value in enumerate(row):
                col = columns[i] if i < len(columns) else {}
                width = col.get("width", 40) if isinstance(col, dict) else 40
                align = col.get("align", "L") if isinstance(col, dict) else "L"
                pdf.cell(width, 6, str(cell_value), border=1, align=align)
            pdf.ln()

        pdf.ln(3)
