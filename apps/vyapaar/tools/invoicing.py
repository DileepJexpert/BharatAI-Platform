"""GST-compliant invoice generation.

Produces invoice data as a dict. PDF generation uses fpdf2 when available
(graceful degradation if not installed).
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone

from .reports import format_amount

logger = logging.getLogger(__name__)

# ── Module-level counter for invoice numbering ─────────────────

_invoice_counter: dict[str, int] = {}  # "YYYY-MM" → count


def reset_invoice_counter() -> None:
    """Reset counter (for tests)."""
    _invoice_counter.clear()


def _amount_in_words(rupees: int) -> str:
    """Convert rupees to words (Indian numbering)."""
    if rupees == 0:
        return "Zero Rupees Only"

    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def _convert(n: int) -> str:
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")
        if n < 1000:
            return ones[n // 100] + " Hundred" + (" " + _convert(n % 100) if n % 100 else "")
        if n < 100000:
            return _convert(n // 1000) + " Thousand" + (" " + _convert(n % 1000) if n % 1000 else "")
        if n < 10000000:
            return _convert(n // 100000) + " Lakh" + (" " + _convert(n % 100000) if n % 100000 else "")
        return _convert(n // 10000000) + " Crore" + (" " + _convert(n % 10000000) if n % 10000000 else "")

    return f"Rupees {_convert(rupees)} Only"


def _next_invoice_number(prefix: str = "VS") -> str:
    """Generate sequential invoice number: VS/{YYYY-MM}/{sequence}."""
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")
    full_prefix = f"{prefix}/{month_key}"
    count = _invoice_counter.get(month_key, 0) + 1
    _invoice_counter[month_key] = count
    return f"{full_prefix}/{count:03d}"


@dataclass
class InvoiceItem:
    product_name: str
    quantity: float
    unit_price_rupees: float
    unit: str = "piece"
    gst_rate: float = 0


def calculate_invoice(
    items: list[dict],
    business_name: str = "",
    contact_name: str = "",
    gstin: str = "",
) -> dict:
    """Calculate invoice totals with GST.

    Each item dict: product_name, quantity, unit_price_rupees, unit, gst_rate.
    Returns complete invoice data dict.
    """
    invoice_number = _next_invoice_number()
    now = datetime.now(timezone.utc)

    subtotal = 0
    total_cgst = 0
    total_sgst = 0
    processed_items = []

    for item in items:
        qty = item.get("quantity", 1)
        unit_price = item.get("unit_price_rupees", 0)
        gst_rate = item.get("gst_rate", 0)
        item_amount = int(qty * unit_price * 100)  # paisa
        cgst = int(item_amount * gst_rate / 200)  # half of GST as CGST
        sgst = cgst  # same state assumed

        subtotal += item_amount
        total_cgst += cgst
        total_sgst += sgst
        processed_items.append({
            "product_name": item.get("product_name", ""),
            "quantity": qty,
            "unit": item.get("unit", "piece"),
            "unit_price_rupees": unit_price,
            "gst_rate": gst_rate,
            "amount_paisa": item_amount,
            "cgst_paisa": cgst,
            "sgst_paisa": sgst,
        })

    total = subtotal + total_cgst + total_sgst

    return {
        "invoice_number": invoice_number,
        "date": now.strftime("%d-%m-%Y"),
        "business_name": business_name,
        "gstin": gstin,
        "contact_name": contact_name,
        "items": processed_items,
        "subtotal_paisa": subtotal,
        "cgst_paisa": total_cgst,
        "sgst_paisa": total_sgst,
        "total_paisa": total,
        "subtotal_display": format_amount(subtotal),
        "cgst_display": format_amount(total_cgst),
        "sgst_display": format_amount(total_sgst),
        "total_display": format_amount(total),
        "amount_in_words": _amount_in_words(total // 100),
    }


def generate_invoice_pdf(invoice_data: dict) -> str | None:
    """Generate PDF from invoice data. Returns file path or None if fpdf2 not available."""
    try:
        from fpdf import FPDF
    except ImportError:
        logger.info("fpdf2 not installed — PDF generation skipped")
        return None

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, invoice_data.get("business_name", ""), ln=True, align="C")
    gstin = invoice_data.get("gstin", "")
    if gstin:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"GSTIN: {gstin}", ln=True, align="C")
    pdf.ln(5)

    # Invoice info
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "TAX INVOICE", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 6, f"Invoice No: {invoice_data['invoice_number']}")
    pdf.cell(95, 6, f"Date: {invoice_data['date']}", ln=True, align="R")
    pdf.ln(3)

    # Bill To
    contact_name = invoice_data.get("contact_name", "")
    if contact_name:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Bill To:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, contact_name, ln=True)
    pdf.ln(5)

    # Table header
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(10, 8, "#", border=1, fill=True, align="C")
    pdf.cell(55, 8, "Item", border=1, fill=True)
    pdf.cell(20, 8, "Qty", border=1, fill=True, align="C")
    pdf.cell(25, 8, "Rate", border=1, fill=True, align="R")
    pdf.cell(20, 8, "GST%", border=1, fill=True, align="C")
    pdf.cell(30, 8, "Amount", border=1, fill=True, align="R")
    pdf.cell(30, 8, "Tax", border=1, fill=True, align="R")
    pdf.ln()

    # Item rows
    pdf.set_font("Helvetica", "", 9)
    for i, item in enumerate(invoice_data["items"], 1):
        pdf.cell(10, 7, str(i), border=1, align="C")
        pdf.cell(55, 7, str(item.get("product_name", ""))[:30], border=1)
        qty_str = f"{item.get('quantity', 1)} {item.get('unit', '')}"
        pdf.cell(20, 7, qty_str, border=1, align="C")
        pdf.cell(25, 7, format_amount(int(item.get("unit_price_rupees", 0) * 100)), border=1, align="R")
        pdf.cell(20, 7, f"{item.get('gst_rate', 0)}%", border=1, align="C")
        pdf.cell(30, 7, format_amount(item["amount_paisa"]), border=1, align="R")
        pdf.cell(30, 7, format_amount(item["cgst_paisa"] + item["sgst_paisa"]), border=1, align="R")
        pdf.ln()

    pdf.ln(3)

    # Totals
    pdf.set_font("Helvetica", "", 10)
    x_label = 120
    pdf.set_x(x_label)
    pdf.cell(40, 6, "Subtotal:", align="R")
    pdf.cell(30, 6, invoice_data["subtotal_display"], align="R", ln=True)
    if invoice_data["cgst_paisa"]:
        pdf.set_x(x_label)
        pdf.cell(40, 6, "CGST:", align="R")
        pdf.cell(30, 6, invoice_data["cgst_display"], align="R", ln=True)
        pdf.set_x(x_label)
        pdf.cell(40, 6, "SGST:", align="R")
        pdf.cell(30, 6, invoice_data["sgst_display"], align="R", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(x_label)
    pdf.cell(40, 8, "Total:", align="R")
    pdf.cell(30, 8, invoice_data["total_display"], align="R", ln=True)

    # Amount in words
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, invoice_data["amount_in_words"], ln=True)

    # Save
    inv_num = invoice_data["invoice_number"].replace("/", "_")
    pdf_path = tempfile.mktemp(suffix=".pdf", prefix=f"invoice_{inv_num}_")
    pdf.output(pdf_path)
    return pdf_path
