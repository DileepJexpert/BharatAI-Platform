"""Report formatting for WhatsApp / text display.

Indian numbering system (lakh, crore) and Hinglish formatting.
"""

from __future__ import annotations


def format_amount(paisa: int) -> str:
    """Format paisa to readable rupees with Indian numbering."""
    rupees = paisa / 100
    if rupees == int(rupees):
        rupees = int(rupees)

    s = str(abs(rupees))
    if "." in s:
        integer_part, decimal_part = s.split(".")
    else:
        integer_part, decimal_part = s, None

    # Indian numbering: last 3 digits, then groups of 2
    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        integer_part = ",".join(groups) + "," + last3

    result = integer_part
    if decimal_part and decimal_part not in ("0", "00"):
        result += "." + decimal_part

    sign = "-" if paisa < 0 else ""
    return f"₹{sign}{result}"


def format_daily_summary(summary: dict) -> str:
    """Format daily summary into Hinglish text.

    Expects dict with keys: date, total_sales, total_purchases,
    total_payments_in, total_payments_out, total_expenses,
    net_position, transaction_count, top_credit_customers, total_outstanding.
    All amounts in paisa.
    """
    lines = [
        f"📊 Aaj ka hisaab — {summary['date']}",
        "",
        f"💰 Bikri: {format_amount(summary['total_sales'])}",
        f"🛒 Khareedari: {format_amount(summary['total_purchases'])}",
        f"💵 Paisa aaya: {format_amount(summary['total_payments_in'])}",
        f"💸 Paisa diya: {format_amount(summary['total_payments_out'])}",
        f"📝 Kharcha: {format_amount(summary['total_expenses'])}",
        "",
    ]

    net = summary["net_position"]
    sign = "+" if net >= 0 else ""
    lines.append(f"📈 Aaj ka net: {sign}{format_amount(net)}")
    lines.append(f"📊 Total transactions: {summary['transaction_count']}")

    top = summary.get("top_credit_customers", [])
    if top:
        lines.append("")
        lines.append("🔴 Sabse zyada udhar:")
        for c in top[:5]:
            lines.append(f"  • {c['name']}: {format_amount(c['balance'])}")

    lines.append("")
    lines.append(f"Total udhar baaki: {format_amount(summary['total_outstanding'])}")
    return "\n".join(lines)


def format_credit_report(report: dict) -> str:
    """Format credit report.

    Expects dict with keys: customers_who_owe (list), total_receivable,
    suppliers_we_owe (list), total_payable. All amounts in paisa.
    """
    lines = ["📋 Udhar Report", ""]

    customers = report.get("customers_who_owe", [])
    if customers:
        lines.append(f"🔴 Jo humein dena hai (Total: {format_amount(report['total_receivable'])}):")
        for c in customers:
            lines.append(f"  • {c['name']}: {format_amount(c['balance'])}")
    else:
        lines.append("✅ Kisi ka udhar nahi hai!")

    suppliers = report.get("suppliers_we_owe", [])
    if suppliers:
        lines.append("")
        lines.append(f"🔵 Jo humein dena hai (Total: {format_amount(report['total_payable'])}):")
        for c in suppliers:
            lines.append(f"  • {c['name']}: {format_amount(abs(c['balance']))}")

    return "\n".join(lines)


def format_transaction_history(transactions: list[dict], contact_name: str) -> str:
    """Format recent transactions with a contact.

    Each transaction dict: type, amount (paisa), date (str).
    """
    if not transactions:
        return f"❌ {contact_name} ke saath koi transaction nahi mila."

    type_emoji = {
        "SALE": "💰", "PURCHASE": "🛒", "PAYMENT_IN": "💵",
        "PAYMENT_OUT": "💸", "EXPENSE": "📝",
    }
    type_hindi = {
        "SALE": "Bikri", "PURCHASE": "Khareedari", "PAYMENT_IN": "Paisa aaya",
        "PAYMENT_OUT": "Paisa diya", "EXPENSE": "Kharcha",
    }

    lines = [f"📜 {contact_name} ke transactions:", ""]
    for t in transactions:
        emoji = type_emoji.get(t["type"], "📝")
        label = type_hindi.get(t["type"], t["type"])
        date_str = t.get("date", "")
        lines.append(f"{emoji} {date_str} — {label}: {format_amount(t['amount'])}")

    return "\n".join(lines)
