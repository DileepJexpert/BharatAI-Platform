"""Tests for Vyapaar Sahayak domain tools — contacts, bookkeeping, catalogue, reports, invoicing."""

import pytest
from datetime import date

from apps.vyapaar.tools.contacts import (
    HINDI_HONORIFICS,
    normalize_name,
    find_contact,
    create_contact,
    get_or_create_contact,
    get_all_contacts,
    get_contacts_with_balance,
    clear_contacts,
)
from apps.vyapaar.tools.bookkeeping import (
    record_sale,
    record_purchase,
    record_payment_in,
    record_payment_out,
    record_expense,
    get_contact_balance,
    get_daily_summary,
    get_credit_report,
    get_transaction_history,
    clear_transactions,
)
from apps.vyapaar.tools.catalogue import (
    add_product,
    find_product,
    update_stock,
    get_low_stock_products,
    get_price_list,
    clear_products,
)
from apps.vyapaar.tools.reports import (
    format_amount,
    format_daily_summary,
    format_credit_report,
    format_transaction_history,
)
from apps.vyapaar.tools.invoicing import (
    _amount_in_words,
    calculate_invoice,
    reset_invoice_counter,
)


@pytest.fixture(autouse=True)
def clean_stores():
    """Reset all in-memory stores before each test."""
    clear_contacts()
    clear_transactions()
    clear_products()
    reset_invoice_counter()
    yield
    clear_contacts()
    clear_transactions()
    clear_products()
    reset_invoice_counter()


class TestContacts:
    """Test contact management and fuzzy matching."""

    def test_normalize_name_strips_honorifics(self):
        assert normalize_name("Sharma Ji") == "sharma"
        assert normalize_name("Ramesh Bhai") == "ramesh"
        assert normalize_name("Sita Didi") == "sita"

    def test_normalize_name_lowercase(self):
        assert normalize_name("RAJU SETH") == "raju"

    def test_hindi_honorifics_completeness(self):
        assert len(HINDI_HONORIFICS) >= 10
        assert "ji" in HINDI_HONORIFICS
        assert "sahab" in HINDI_HONORIFICS
        assert "bhai" in HINDI_HONORIFICS

    def test_create_contact(self):
        c = create_contact("Sharma Ji", "customer", "9876543210")
        assert c.name == "Sharma Ji"
        assert c.name_normalized == "sharma"
        assert c.phone_number == "9876543210"
        assert c.contact_type == "customer"
        assert c.running_balance == 0

    def test_find_contact_exact(self):
        create_contact("Ramesh")
        result = find_contact("Ramesh")
        assert result.match_type == "exact"
        assert result.contact.name == "Ramesh"

    def test_find_contact_with_honorific(self):
        create_contact("Ramesh")
        result = find_contact("Ramesh Ji")
        assert result.match_type == "exact"
        assert result.contact.name == "Ramesh"

    def test_find_contact_fuzzy(self):
        create_contact("Ramesh Kumar")
        result = find_contact("Ramesh")
        assert result.match_type in ("fuzzy", "exact")
        assert result.contact is not None

    def test_find_contact_not_found(self):
        result = find_contact("NonexistentPerson")
        assert result.match_type == "none"

    def test_get_or_create(self):
        c1 = get_or_create_contact("Sharma")
        c2 = get_or_create_contact("Sharma")
        assert c1.id == c2.id
        assert len(get_all_contacts()) == 1

    def test_get_contacts_with_balance(self):
        c = create_contact("Sharma")
        c.running_balance = 50000  # 500 rupees
        result = get_contacts_with_balance()
        assert len(result) == 1
        assert result[0].name == "Sharma"


class TestBookkeeping:
    """Test bookkeeping transaction recording."""

    def test_record_sale_credit(self):
        result = record_sale("Sharma Ji", 5000, payment_mode="credit")
        assert result.transaction.type == "SALE"
        assert result.transaction.amount == 500000  # paisa
        assert result.contact.name == "Sharma Ji"
        assert result.new_balance == 500000  # they owe us 5000

    def test_record_sale_cash(self):
        result = record_sale("Ramesh", 2000, payment_mode="cash")
        assert result.transaction.type == "SALE"
        assert result.new_balance == 0  # cash, no balance change

    def test_record_purchase_credit(self):
        result = record_purchase("Supplier A", 10000, payment_mode="credit")
        assert result.transaction.type == "PURCHASE"
        assert result.new_balance == -1000000  # we owe them

    def test_record_payment_in(self):
        record_sale("Sharma", 5000, payment_mode="credit")
        result = record_payment_in("Sharma", 3000)
        assert result.transaction.type == "PAYMENT_IN"
        assert result.new_balance == 200000  # 5000-3000 = 2000 still owed

    def test_record_payment_out(self):
        record_purchase("Supplier A", 10000, payment_mode="credit")
        result = record_payment_out("Supplier A", 5000)
        assert result.transaction.type == "PAYMENT_OUT"
        assert result.new_balance == -500000  # still owe 5000

    def test_record_expense(self):
        result = record_expense(1500, description="Bijli ka bill")
        assert result.transaction.type == "EXPENSE"
        assert result.transaction.amount == 150000
        assert result.contact is None

    def test_get_contact_balance(self):
        record_sale("Sharma", 5000, payment_mode="credit")
        record_payment_in("Sharma", 2000)
        balance = get_contact_balance("Sharma")
        assert balance is not None
        assert balance["balance_rupees"] == 3000.0
        assert len(balance["transactions"]) == 2

    def test_get_contact_balance_not_found(self):
        assert get_contact_balance("NonexistentPerson") is None

    def test_get_daily_summary(self):
        record_sale("Sharma", 5000, payment_mode="credit")
        record_purchase("Supplier A", 2000, payment_mode="cash")
        record_expense(500)
        summary = get_daily_summary()
        assert summary.total_sales == 500000
        assert summary.total_purchases == 200000
        assert summary.total_expenses == 50000
        assert summary.transaction_count == 3
        assert summary.net_position == 500000 - 200000 - 50000

    def test_get_daily_summary_empty(self):
        summary = get_daily_summary()
        assert summary.transaction_count == 0
        assert summary.net_position == 0

    def test_get_credit_report(self):
        record_sale("Sharma", 5000, payment_mode="credit")
        record_sale("Raju", 3000, payment_mode="credit")
        record_purchase("Supplier A", 8000, payment_mode="credit")
        report = get_credit_report()
        assert len(report.customers_who_owe) == 2
        assert report.total_receivable == 800000  # 5000+3000 in paisa
        assert len(report.suppliers_we_owe) == 1
        assert report.total_payable == 800000

    def test_get_transaction_history(self):
        record_sale("Sharma", 5000, payment_mode="credit")
        record_payment_in("Sharma", 2000)
        history = get_transaction_history("Sharma")
        assert len(history) == 2
        assert history[0]["type"] == "PAYMENT_IN"  # most recent first
        assert history[1]["type"] == "SALE"

    def test_stock_deduction_on_sale(self):
        add_product("Cement", 400, unit="bag", current_stock=50, low_stock_threshold=10)
        result = record_sale("Sharma", 2000, product_name="Cement", quantity=5, unit="bag")
        product = find_product("Cement")
        assert product.current_stock == 45

    def test_stock_addition_on_purchase(self):
        add_product("Cement", 400, unit="bag", current_stock=50)
        record_purchase("Supplier A", 8000, product_name="Cement", quantity=20, unit="bag")
        product = find_product("Cement")
        assert product.current_stock == 70

    def test_low_stock_alert(self):
        add_product("Cement", 400, unit="bag", current_stock=12, low_stock_threshold=10)
        result = record_sale("Sharma", 1200, product_name="Cement", quantity=5, unit="bag")
        assert len(result.alerts) == 1
        assert "Stock kam hai" in result.alerts[0]


class TestCatalogue:
    """Test product catalogue and stock management."""

    def test_add_product(self):
        p = add_product("Cement", 400, unit="bag", current_stock=100)
        assert p.name == "Cement"
        assert p.selling_price == 40000
        assert p.unit == "bag"
        assert p.current_stock == 100

    def test_find_product_exact(self):
        add_product("Cement", 400)
        result = find_product("Cement")
        assert result is not None
        assert result.name == "Cement"

    def test_find_product_fuzzy(self):
        add_product("White Cement", 500)
        result = find_product("white cement")
        assert result is not None
        assert result.name == "White Cement"

    def test_find_product_not_found(self):
        assert find_product("NonexistentProduct") is None

    def test_update_stock_add(self):
        add_product("Cement", 400, current_stock=50)
        result = update_stock("Cement", 20)
        assert result.new_stock == 70
        assert result.is_low_stock is False

    def test_update_stock_deduct(self):
        add_product("Cement", 400, current_stock=50, low_stock_threshold=10)
        result = update_stock("Cement", -45)
        assert result.new_stock == 5
        assert result.is_low_stock is True

    def test_update_stock_floor_zero(self):
        add_product("Cement", 400, current_stock=5)
        result = update_stock("Cement", -10)
        assert result.new_stock == 0

    def test_get_low_stock(self):
        add_product("Cement", 400, current_stock=5, low_stock_threshold=10)
        add_product("Sand", 200, current_stock=100, low_stock_threshold=20)
        low = get_low_stock_products()
        assert len(low) == 1
        assert low[0].name == "Cement"

    def test_get_price_list(self):
        add_product("Cement", 400)
        add_product("Sand", 200)
        add_product("Bricks", 8)
        prices = get_price_list()
        assert len(prices) == 3
        assert prices[0].name == "Bricks"  # alphabetical

    def test_add_product_with_gst(self):
        p = add_product("Cement", 400, gst_rate=18)
        assert p.gst_rate == 18


class TestReports:
    """Test report formatting."""

    def test_format_amount_basic(self):
        assert format_amount(10000) == "₹100"
        assert format_amount(500000) == "₹5,000"

    def test_format_amount_indian_numbering(self):
        assert format_amount(10000000) == "₹1,00,000"
        assert format_amount(100000000) == "₹10,00,000"

    def test_format_amount_negative(self):
        assert format_amount(-50000) == "₹-500"

    def test_format_amount_with_paise(self):
        assert format_amount(10050) == "₹100.5"

    def test_format_daily_summary(self):
        summary = {
            "date": "2026-04-10",
            "total_sales": 500000,
            "total_purchases": 200000,
            "total_payments_in": 100000,
            "total_payments_out": 50000,
            "total_expenses": 30000,
            "net_position": 320000,
            "transaction_count": 5,
            "top_credit_customers": [{"name": "Sharma", "balance": 300000}],
            "total_outstanding": 300000,
        }
        text = format_daily_summary(summary)
        assert "Aaj ka hisaab" in text
        assert "Bikri" in text
        assert "Sharma" in text

    def test_format_credit_report(self):
        report = {
            "customers_who_owe": [{"name": "Sharma", "balance": 500000}],
            "total_receivable": 500000,
            "suppliers_we_owe": [{"name": "Supplier A", "balance": -300000}],
            "total_payable": 300000,
        }
        text = format_credit_report(report)
        assert "Udhar Report" in text
        assert "Sharma" in text
        assert "Supplier A" in text

    def test_format_credit_report_no_debts(self):
        report = {
            "customers_who_owe": [],
            "total_receivable": 0,
            "suppliers_we_owe": [],
            "total_payable": 0,
        }
        text = format_credit_report(report)
        assert "Kisi ka udhar nahi hai" in text

    def test_format_transaction_history(self):
        txns = [
            {"type": "SALE", "amount": 500000, "date": "10 Apr"},
            {"type": "PAYMENT_IN", "amount": 200000, "date": "10 Apr"},
        ]
        text = format_transaction_history(txns, "Sharma")
        assert "Sharma ke transactions" in text
        assert "Bikri" in text
        assert "Paisa aaya" in text

    def test_format_transaction_history_empty(self):
        text = format_transaction_history([], "Sharma")
        assert "koi transaction nahi mila" in text


class TestInvoicing:
    """Test invoice generation."""

    def test_amount_in_words_zero(self):
        assert _amount_in_words(0) == "Zero Rupees Only"

    def test_amount_in_words_basic(self):
        assert _amount_in_words(100) == "Rupees One Hundred Only"
        assert _amount_in_words(5000) == "Rupees Five Thousand Only"

    def test_amount_in_words_lakh(self):
        result = _amount_in_words(100000)
        assert "Lakh" in result

    def test_amount_in_words_crore(self):
        result = _amount_in_words(10000000)
        assert "Crore" in result

    def test_calculate_invoice_no_gst(self):
        items = [
            {"product_name": "Cement", "quantity": 10, "unit_price_rupees": 400, "unit": "bag", "gst_rate": 0},
        ]
        invoice = calculate_invoice(items, business_name="Test Store")
        assert invoice["subtotal_paisa"] == 400000  # 10 * 400 * 100
        assert invoice["cgst_paisa"] == 0
        assert invoice["sgst_paisa"] == 0
        assert invoice["total_paisa"] == 400000
        assert "VS/" in invoice["invoice_number"]

    def test_calculate_invoice_with_gst(self):
        items = [
            {"product_name": "Cement", "quantity": 10, "unit_price_rupees": 400, "gst_rate": 18},
        ]
        invoice = calculate_invoice(items, business_name="Test Store", gstin="22AAAAA0000A1Z5")
        assert invoice["subtotal_paisa"] == 400000
        # CGST = 400000 * 18 / 200 = 36000
        assert invoice["cgst_paisa"] == 36000
        assert invoice["sgst_paisa"] == 36000
        assert invoice["total_paisa"] == 400000 + 36000 + 36000
        assert invoice["gstin"] == "22AAAAA0000A1Z5"

    def test_calculate_invoice_multiple_items(self):
        items = [
            {"product_name": "Cement", "quantity": 10, "unit_price_rupees": 400, "gst_rate": 18},
            {"product_name": "Sand", "quantity": 5, "unit_price_rupees": 200, "gst_rate": 5},
        ]
        invoice = calculate_invoice(items)
        assert len(invoice["items"]) == 2
        assert invoice["total_paisa"] > 0

    def test_invoice_number_sequential(self):
        items = [{"product_name": "A", "quantity": 1, "unit_price_rupees": 100, "gst_rate": 0}]
        inv1 = calculate_invoice(items)
        inv2 = calculate_invoice(items)
        assert inv1["invoice_number"].endswith("/001")
        assert inv2["invoice_number"].endswith("/002")

    def test_invoice_has_amount_in_words(self):
        items = [{"product_name": "Cement", "quantity": 10, "unit_price_rupees": 400, "gst_rate": 0}]
        invoice = calculate_invoice(items)
        assert "Rupees" in invoice["amount_in_words"]
        assert "Only" in invoice["amount_in_words"]

    def test_invoice_display_fields(self):
        items = [{"product_name": "Cement", "quantity": 1, "unit_price_rupees": 1000, "gst_rate": 0}]
        invoice = calculate_invoice(items)
        assert "₹" in invoice["subtotal_display"]
        assert "₹" in invoice["total_display"]
