"""Product catalogue and stock management.

Standalone in-memory store for testing; real deployments use the DB layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from uuid import uuid4


@dataclass
class Product:
    """In-memory product record."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    name_normalized: str = ""
    selling_price: int = 0  # paisa
    purchase_price: int | None = None  # paisa
    unit: str = "piece"
    current_stock: float = 0
    low_stock_threshold: float | None = None
    gst_rate: float = 0  # percentage
    is_active: bool = True


@dataclass
class StockResult:
    product: Product
    new_stock: float
    is_low_stock: bool


# ── In-memory store ────────────────────────────────────────────

_products: list[Product] = []


def clear_products() -> None:
    """Reset store (for tests)."""
    _products.clear()


def _normalize(name: str) -> str:
    return name.lower().strip()


def add_product(
    name: str,
    selling_price_rupees: float,
    unit: str = "piece",
    current_stock: float = 0,
    purchase_price_rupees: float | None = None,
    low_stock_threshold: float | None = None,
    gst_rate: float = 0,
) -> Product:
    """Add a new product to the catalogue."""
    product = Product(
        name=name,
        name_normalized=_normalize(name),
        selling_price=int(selling_price_rupees * 100),
        purchase_price=int(purchase_price_rupees * 100) if purchase_price_rupees else None,
        unit=unit,
        current_stock=current_stock,
        low_stock_threshold=low_stock_threshold,
        gst_rate=gst_rate,
    )
    _products.append(product)
    return product


def find_product(product_name: str) -> Product | list[Product] | None:
    """Fuzzy-match product name. Returns single match, list of ambiguous, or None."""
    normalized = _normalize(product_name)
    active = [p for p in _products if p.is_active]

    if not active:
        return None

    # Exact match
    for p in active:
        if p.name_normalized == normalized:
            return p

    # Contains match
    contains = [
        p for p in active
        if normalized in p.name_normalized or p.name_normalized in normalized
    ]
    if len(contains) == 1:
        return contains[0]

    # Fuzzy match
    scored = []
    for p in active:
        ratio = SequenceMatcher(None, normalized, p.name_normalized).ratio()
        if ratio > 0.7:
            scored.append((p, ratio))

    scored.sort(key=lambda x: x[1], reverse=True)
    if len(scored) == 1:
        return scored[0][0]
    if len(scored) > 1:
        if scored[0][1] - scored[1][1] > 0.15:
            return scored[0][0]
        return [s[0] for s in scored[:5]]

    if len(contains) > 1:
        return contains[:5]

    return None


def update_stock(product_name: str, quantity_change: float) -> StockResult | None:
    """Update stock. Positive = add, negative = deduct."""
    product = find_product(product_name)
    if not product or isinstance(product, list):
        return None

    product.current_stock += quantity_change
    if product.current_stock < 0:
        product.current_stock = 0

    is_low = (
        product.low_stock_threshold is not None
        and product.current_stock <= product.low_stock_threshold
    )
    return StockResult(product=product, new_stock=product.current_stock, is_low_stock=is_low)


def get_low_stock_products() -> list[Product]:
    """All products where current_stock <= threshold."""
    return [
        p for p in _products
        if p.is_active
        and p.low_stock_threshold is not None
        and p.current_stock <= p.low_stock_threshold
    ]


def get_price_list() -> list[Product]:
    """All active products sorted by name."""
    return sorted(
        [p for p in _products if p.is_active],
        key=lambda p: p.name,
    )
