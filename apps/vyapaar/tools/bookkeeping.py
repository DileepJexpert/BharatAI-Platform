"""Core bookkeeping engine. All amounts stored in paisa.

Standalone in-memory store for testing; real deployments use the DB layer.
Transaction types: SALE, PURCHASE, PAYMENT_IN, PAYMENT_OUT, EXPENSE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import uuid4

from .contacts import Contact, get_or_create_contact, get_all_contacts


@dataclass
class Transaction:
    """In-memory transaction record."""
    id: str = field(default_factory=lambda: str(uuid4()))
    contact_name: str | None = None
    type: str = ""  # SALE, PURCHASE, PAYMENT_IN, PAYMENT_OUT, EXPENSE
    amount: int = 0  # paisa
    payment_mode: str = "credit"
    description: str | None = None
    product_name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    date: str = field(default_factory=lambda: date.today().isoformat())
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TransactionResult:
    transaction: Transaction
    contact: Contact | None
    new_balance: int  # paisa
    alerts: list[str]


@dataclass
class DailySummary:
    date: str
    total_sales: int  # paisa
    total_purchases: int
    total_payments_in: int
    total_payments_out: int
    total_expenses: int
    net_position: int
    transaction_count: int
    top_credit_customers: list[dict]
    total_outstanding: int


@dataclass
class CreditReport:
    customers_who_owe: list[dict]
    total_receivable: int  # paisa
    suppliers_we_owe: list[dict]
    total_payable: int


# ── In-memory store ────────────────────────────────────────────

_transactions: list[Transaction] = []


def clear_transactions() -> None:
    """Reset store (for tests)."""
    _transactions.clear()


def get_all_transactions() -> list[Transaction]:
    """Return all transactions."""
    return list(_transactions)


# ── Transaction recording ──────────────────────────────────────


def record_sale(
    contact_name: str,
    amount_rupees: float,
    payment_mode: str = "credit",
    description: str | None = None,
    product_name: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
) -> TransactionResult:
    """Record a sale. If credit, increase contact balance (they owe more)."""
    amount_paisa = int(amount_rupees * 100)
    contact = get_or_create_contact(contact_name, "customer")

    txn = Transaction(
        contact_name=contact.name,
        type="SALE",
        amount=amount_paisa,
        payment_mode=payment_mode,
        description=description,
        product_name=product_name,
        quantity=quantity,
        unit=unit,
    )
    _transactions.append(txn)

    alerts: list[str] = []
    if payment_mode == "credit":
        contact.running_balance += amount_paisa

    # Stock deduction
    if product_name and quantity:
        alerts.extend(_deduct_stock(product_name, quantity))

    return TransactionResult(
        transaction=txn, contact=contact, new_balance=contact.running_balance, alerts=alerts
    )


def record_purchase(
    contact_name: str,
    amount_rupees: float,
    payment_mode: str = "credit",
    description: str | None = None,
    product_name: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
) -> TransactionResult:
    """Record a purchase. If credit, decrease contact balance (we owe more)."""
    amount_paisa = int(amount_rupees * 100)
    contact = get_or_create_contact(contact_name, "supplier")

    txn = Transaction(
        contact_name=contact.name,
        type="PURCHASE",
        amount=amount_paisa,
        payment_mode=payment_mode,
        description=description,
        product_name=product_name,
        quantity=quantity,
        unit=unit,
    )
    _transactions.append(txn)

    if payment_mode == "credit":
        contact.running_balance -= amount_paisa

    # Stock addition
    if product_name and quantity:
        _add_stock(product_name, quantity)

    return TransactionResult(
        transaction=txn, contact=contact, new_balance=contact.running_balance, alerts=[]
    )


def record_payment_in(
    contact_name: str,
    amount_rupees: float,
    payment_mode: str = "cash",
) -> TransactionResult:
    """Customer paid us. Decrease their balance (they owe less)."""
    amount_paisa = int(amount_rupees * 100)
    contact = get_or_create_contact(contact_name, "customer")

    txn = Transaction(
        contact_name=contact.name,
        type="PAYMENT_IN",
        amount=amount_paisa,
        payment_mode=payment_mode,
    )
    _transactions.append(txn)
    contact.running_balance -= amount_paisa

    return TransactionResult(
        transaction=txn, contact=contact, new_balance=contact.running_balance, alerts=[]
    )


def record_payment_out(
    contact_name: str,
    amount_rupees: float,
    payment_mode: str = "cash",
) -> TransactionResult:
    """We paid supplier. Increase balance toward 0 (we owe less)."""
    amount_paisa = int(amount_rupees * 100)
    contact = get_or_create_contact(contact_name, "supplier")

    txn = Transaction(
        contact_name=contact.name,
        type="PAYMENT_OUT",
        amount=amount_paisa,
        payment_mode=payment_mode,
    )
    _transactions.append(txn)
    contact.running_balance += amount_paisa

    return TransactionResult(
        transaction=txn, contact=contact, new_balance=contact.running_balance, alerts=[]
    )


def record_expense(
    amount_rupees: float,
    description: str | None = None,
) -> TransactionResult:
    """Business expense. No contact involved."""
    amount_paisa = int(amount_rupees * 100)

    txn = Transaction(
        type="EXPENSE",
        amount=amount_paisa,
        payment_mode="cash",
        description=description,
    )
    _transactions.append(txn)

    return TransactionResult(transaction=txn, contact=None, new_balance=0, alerts=[])


# ── Queries ────────────────────────────────────────────────────


def get_contact_balance(contact_name: str) -> dict | None:
    """Return contact balance + last 5 transactions."""
    from .contacts import find_contact

    match = find_contact(contact_name)
    if match.match_type == "none" or not match.contact:
        return None

    contact = match.contact
    contact_txns = [
        t for t in reversed(_transactions)
        if t.contact_name == contact.name
    ][:5]

    return {
        "contact_name": contact.name,
        "balance_paisa": contact.running_balance,
        "balance_rupees": contact.running_balance / 100,
        "transactions": [
            {"type": t.type, "amount": t.amount, "date": t.date, "payment_mode": t.payment_mode}
            for t in contact_txns
        ],
    }


def get_daily_summary(target_date: date | None = None) -> DailySummary:
    """Aggregate all transactions for a given date."""
    target = target_date or date.today()
    target_str = target.isoformat()

    day_txns = [t for t in _transactions if t.date == target_str]

    sales = sum(t.amount for t in day_txns if t.type == "SALE")
    purchases = sum(t.amount for t in day_txns if t.type == "PURCHASE")
    payments_in = sum(t.amount for t in day_txns if t.type == "PAYMENT_IN")
    payments_out = sum(t.amount for t in day_txns if t.type == "PAYMENT_OUT")
    expenses = sum(t.amount for t in day_txns if t.type == "EXPENSE")

    # Top credit customers
    contacts = get_all_contacts()
    top_customers = sorted(
        [c for c in contacts if c.running_balance > 0],
        key=lambda c: c.running_balance,
        reverse=True,
    )[:5]

    total_outstanding = sum(c.running_balance for c in contacts if c.running_balance > 0)

    return DailySummary(
        date=target_str,
        total_sales=sales,
        total_purchases=purchases,
        total_payments_in=payments_in,
        total_payments_out=payments_out,
        total_expenses=expenses,
        net_position=sales + payments_in - purchases - payments_out - expenses,
        transaction_count=len(day_txns),
        top_credit_customers=[
            {"name": c.name, "balance": c.running_balance}
            for c in top_customers
        ],
        total_outstanding=total_outstanding,
    )


def get_credit_report() -> CreditReport:
    """All contacts with running_balance != 0."""
    contacts = get_all_contacts()

    customers_who_owe = [
        {"name": c.name, "balance": c.running_balance, "phone": c.phone_number}
        for c in sorted(
            [c for c in contacts if c.running_balance > 0],
            key=lambda c: c.running_balance,
            reverse=True,
        )
    ]
    suppliers_we_owe = [
        {"name": c.name, "balance": c.running_balance, "phone": c.phone_number}
        for c in sorted(
            [c for c in contacts if c.running_balance < 0],
            key=lambda c: c.running_balance,
        )
    ]

    return CreditReport(
        customers_who_owe=customers_who_owe,
        total_receivable=sum(d["balance"] for d in customers_who_owe),
        suppliers_we_owe=suppliers_we_owe,
        total_payable=abs(sum(d["balance"] for d in suppliers_we_owe)),
    )


def get_transaction_history(contact_name: str, limit: int = 10) -> list[dict]:
    """Last N transactions with a specific contact."""
    from .contacts import find_contact

    match = find_contact(contact_name)
    if not match.contact:
        return []

    contact_txns = [
        t for t in reversed(_transactions)
        if t.contact_name == match.contact.name
    ][:limit]

    return [
        {"type": t.type, "amount": t.amount, "date": t.date, "payment_mode": t.payment_mode}
        for t in contact_txns
    ]


# ── Stock helpers ──────────────────────────────────────────────


def _deduct_stock(product_name: str, quantity: float) -> list[str]:
    """Deduct stock and return alerts."""
    from .catalogue import find_product, update_stock

    product = find_product(product_name)
    if product and not isinstance(product, list):
        result = update_stock(product_name, -quantity)
        if result and result.is_low_stock:
            return [
                f"⚠️ Stock kam hai: {product.name} — {product.current_stock} {product.unit} bacha"
            ]
    return []


def _add_stock(product_name: str, quantity: float) -> None:
    """Add stock on purchase."""
    from .catalogue import find_product, update_stock

    product = find_product(product_name)
    if product and not isinstance(product, list):
        update_stock(product_name, quantity)
