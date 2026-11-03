"""Product service: business logic for the Products feature.

This module is intentionally free of any Qt imports so it can be tested in
isolation with a plain ``sqlite3`` connection.

Design choices
--------------
- **Typed errors instead of raised exceptions.** Each mutating method
  returns a :class:`Result` whose ``ok`` is the value on success or whose
  ``error`` is a typed ``ServiceError`` subclass (e.g. :class:`DuplicateSKUError`)
  on failure. Read-only methods that cannot meaningfully fail return their
  value directly; ``get_product`` returns ``None`` when not found rather than
  raising. This keeps the UI's error handling declarative and testable.

- **Connection is passed in.** Every method takes the ``sqlite3.Connection``
  it should use. The UI layer owns the connection (opened via
  :func:`src.database.connection.open_connection`) and refreshes pages by
  calling the read methods; tests pass a throwaway connection. The service
  commits its own writes (single-statement transactions are fine here) so the
  caller does not need to remember to commit.

- **DB constraints are a safety net, not the primary UX.** The service
  validates *before* writing (non-empty name, prices/quantity/min_stock >= 0,
  unique SKU/barcode) and returns typed errors, so the UI shows inline
  messages. The DB CHECK/UNIQUE constraints still catch anything the service
  missed.

- **Archiving, never hard-deleting.** :func:`archive_product` sets
  ``is_archived = 1``. No product is ever ``DELETE``d, even one with no
  history -- safe and simple.

- **No stock movements on create/edit in Phase 4.** Creating a product with
  an initial quantity stores the quantity directly on the row but does NOT
  write a ``stock_movements`` row. See the TODO referencing Phase 6.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Typed errors
# --------------------------------------------------------------------------- #
class ServiceError(Exception):
    """Base class for service errors returned via :class:`Result`."""


@dataclass(frozen=True)
class ValidationError(ServiceError):
    """One or more fields failed validation. ``fields`` maps field -> message."""
    fields: dict[str, str]

    def __str__(self) -> str:
        return "; ".join(f"{k}: {v}" for k, v in self.fields.items())


@dataclass(frozen=True)
class DuplicateSKUError(ServiceError):
    sku: str

    def __str__(self) -> str:
        return f"SKU already exists: {self.sku}"


@dataclass(frozen=True)
class DuplicateBarcodeError(ServiceError):
    barcode: str

    def __str__(self) -> str:
        return f"Barcode already exists: {self.barcode}"


@dataclass(frozen=True)
class ProductNotFoundError(ServiceError):
    product_id: int

    def __str__(self) -> str:
        return f"Product not found (id={self.product_id})"


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #
@dataclass
class Result(Generic[T]):
    """A simple success/failure container.

    Use :func:`ok` / :func:`fail` to construct; inspect via ``.ok`` / ``.error``.
    """
    ok: T | None
    error: ServiceError | None

    @property
    def is_ok(self) -> bool:
        return self.error is None

    @property
    def is_fail(self) -> bool:
        return self.error is not None


def ok(value: T) -> Result[T]:
    return Result(ok=value, error=None)


def fail(error: ServiceError) -> Result[T]:  # type: ignore[type-var]
    return Result(ok=None, error=error)


# --------------------------------------------------------------------------- #
# Product row model (a thin read DTO)
# --------------------------------------------------------------------------- #
@dataclass
class Product:
    id: int
    name: str
    sku: str | None
    barcode: str | None
    category_id: int | None
    category_name: str | None
    purchase_price_paise: int
    selling_price_paise: int
    quantity: int
    min_stock: int
    unit: str | None
    description: str | None
    is_archived: int  # 0/1
    created_at: str
    updated_at: str

    @property
    def archived(self) -> bool:
        return bool(self.is_archived)

    @property
    def low_stock(self) -> bool:
        """True when stock is at or below the minimum-stock threshold."""
        return self.quantity <= self.min_stock


def _row_to_product(row: sqlite3.Row) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        sku=row["sku"],
        barcode=row["barcode"],
        category_id=row["category_id"],
        category_name=row["category_name"] if "category_name" in row.keys() else None,
        purchase_price_paise=row["purchase_price_paise"],
        selling_price_paise=row["selling_price_paise"],
        quantity=row["quantity"],
        min_stock=row["min_stock"],
        unit=row["unit"],
        description=row["description"],
        is_archived=row["is_archived"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# --------------------------------------------------------------------------- #
# Sorting / search helpers
# --------------------------------------------------------------------------- #
SORT_COLUMNS: dict[str, str] = {
    "name": "p.name",
    "sku": "p.sku",
    "category": "category_name",
    "quantity": "p.quantity",
    "min_stock": "p.min_stock",
    "selling_price": "p.selling_price_paise",
    "purchase_price": "p.purchase_price_paise",
    "updated_at": "p.updated_at",
}
VALID_SORT_DIRECTIONS = {"asc", "desc"}


def _validate_sort(sort_by: str | None, sort_dir: str) -> tuple[str, str]:
    """Return a (column_sql, direction_sql) pair safe to interpolate into SQL.

    Sort fields are whitelisted to avoid SQL injection via column names.
    """
    if sort_by is None:
        sort_by = "name"
    column = SORT_COLUMNS.get(sort_by)
    if column is None:
        raise ValueError(f"invalid sort_by: {sort_by!r}")
    direction = sort_dir.lower()
    if direction not in VALID_SORT_DIRECTIONS:
        raise ValueError(f"invalid sort_dir: {sort_dir!r}")
    return column, direction


# --------------------------------------------------------------------------- #
# Validation (shared by create/update)
# --------------------------------------------------------------------------- #
def _validate_fields(
    conn: sqlite3.Connection,
    *,
    name: str,
    purchase_price_paise: int,
    selling_price_paise: int,
    quantity: int,
    min_stock: int,
    sku: str | None,
    barcode: str | None,
    exclude_product_id: int | None = None,
) -> ServiceError | None:
    """Return a :class:`ServiceError` if invalid, else ``None``.

    Performs cross-field and uniqueness checks; ``exclude_product_id`` is
    used by ``update`` so a product's own SKU/barcode is not flagged as a
    duplicate of itself.
    """
    errors: dict[str, str] = {}

    if not name or not name.strip():
        errors["name"] = "Name is required."
    elif len(name.strip()) > 255:
        errors["name"] = "Name must be 255 characters or fewer."

    if purchase_price_paise < 0:
        errors["purchase_price"] = "Purchase price cannot be negative."
    if selling_price_paise < 0:
        errors["selling_price"] = "Selling price cannot be negative."
    if quantity < 0:
        errors["quantity"] = "Quantity cannot be negative."
    if min_stock < 0:
        errors["min_stock"] = "Minimum stock cannot be negative."

    if sku is not None and sku.strip() != "":
        sku_clean = sku.strip()
        if _sku_exists(conn, sku_clean, exclude=exclude_product_id):
            errors["sku"] = "This SKU is already in use."
    if barcode is not None and barcode.strip() != "":
        bc_clean = barcode.strip()
        if _barcode_exists(conn, bc_clean, exclude=exclude_product_id):
            errors["barcode"] = "This barcode is already in use."

    if errors:
        return ValidationError(fields=errors)
    return None


def _sku_exists(conn: sqlite3.Connection, sku: str, exclude: int | None = None) -> bool:
    if exclude is None:
        row = conn.execute("SELECT 1 FROM products WHERE sku = ? LIMIT 1", (sku,)).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM products WHERE sku = ? AND id != ? LIMIT 1", (sku, exclude)
        ).fetchone()
    return row is not None


def _barcode_exists(conn: sqlite3.Connection, barcode: str, exclude: int | None = None) -> bool:
    if exclude is None:
        row = conn.execute("SELECT 1 FROM products WHERE barcode = ? LIMIT 1", (barcode,)).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM products WHERE barcode = ? AND id != ? LIMIT 1", (barcode, exclude)
        ).fetchone()
    return row is not None


def _norm_optional(value: str | None) -> str | None:
    """Return a stripped non-empty string or ``None`` for an optional field."""
    if value is None:
        return None
    v = value.strip()
    return v or None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def create_product(
    conn: sqlite3.Connection,
    *,
    name: str,
    sku: str | None = None,
    barcode: str | None = None,
    category_id: int | None = None,
    purchase_price_paise: int = 0,
    selling_price_paise: int = 0,
    quantity: int = 0,
    min_stock: int = 0,
    unit: str | None = None,
    description: str | None = None,
) -> Result[Product]:
    """Create a product. Returns a :class:`Result` with the new product or an error."""
    sku = _norm_optional(sku)
    barcode = _norm_optional(barcode)
    name_stripped = name.strip() if name else ""

    err = _validate_fields(
        conn,
        name=name_stripped,
        purchase_price_paise=purchase_price_paise,
        selling_price_paise=selling_price_paise,
        quantity=quantity,
        min_stock=min_stock,
        sku=sku,
        barcode=barcode,
    )
    if err is not None:
        return fail(err)

    # Verify category exists if provided.
    if category_id is not None:
        row = conn.execute(
            "SELECT 1 FROM categories WHERE id = ? AND is_archived = 0", (category_id,)
        ).fetchone()
        if row is None:
            return fail(ValidationError(fields={"category": "Category not found or archived."}))

    cur = conn.execute(
        """
        INSERT INTO products
            (name, sku, barcode, category_id, purchase_price_paise,
             selling_price_paise, quantity, min_stock, unit, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name_stripped,
            sku,
            barcode,
            category_id,
            purchase_price_paise,
            selling_price_paise,
            quantity,
            min_stock,
            _norm_optional(unit),
            _norm_optional(description),
        ),
    )
    conn.commit()
    product_id = cur.lastrowid
    # TODO(Phase 6): if `quantity > 0`, write an 'opening' stock_movement row
    # referencing this product. Intentionally NOT done in Phase 4 so opening
    # stock + stock movements land together in Phase 6.
    return ok(get_product(conn, product_id))  # type: ignore[return-value]


def update_product(
    conn: sqlite3.Connection,
    product_id: int,
    *,
    name: str,
    sku: str | None = None,
    barcode: str | None = None,
    category_id: int | None = None,
    purchase_price_paise: int = 0,
    selling_price_paise: int = 0,
    quantity: int = 0,
    min_stock: int = 0,
    unit: str | None = None,
    description: str | None = None,
) -> Result[Product]:
    """Update an existing product. Returns a :class:`Result` with the updated product or an error."""
    existing = get_product(conn, product_id)
    if existing is None:
        return fail(ProductNotFoundError(product_id=product_id))

    sku = _norm_optional(sku)
    barcode = _norm_optional(barcode)
    name_stripped = name.strip() if name else ""

    err = _validate_fields(
        conn,
        name=name_stripped,
        purchase_price_paise=purchase_price_paise,
        selling_price_paise=selling_price_paise,
        quantity=quantity,
        min_stock=min_stock,
        sku=sku,
        barcode=barcode,
        exclude_product_id=product_id,
    )
    if err is not None:
        return fail(err)

    if category_id is not None:
        row = conn.execute(
            "SELECT 1 FROM categories WHERE id = ? AND is_archived = 0", (category_id,)
        ).fetchone()
        if row is None:
            return fail(ValidationError(fields={"category": "Category not found or archived."}))

    conn.execute(
        """
        UPDATE products SET
            name = ?, sku = ?, barcode = ?, category_id = ?,
            purchase_price_paise = ?, selling_price_paise = ?,
            quantity = ?, min_stock = ?, unit = ?, description = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
        WHERE id = ?
        """,
        (
            name_stripped,
            sku,
            barcode,
            category_id,
            purchase_price_paise,
            selling_price_paise,
            quantity,
            min_stock,
            _norm_optional(unit),
            _norm_optional(description),
            product_id,
        ),
    )
    conn.commit()
    # TODO(Phase 6): if quantity changed vs `existing.quantity`, write a
    # 'correction' stock_movement row. Intentionally NOT done in Phase 4.
    return ok(get_product(conn, product_id))  # type: ignore[return-value]


def archive_product(conn: sqlite3.Connection, product_id: int) -> Result[None]:
    """Soft-archive a product (set is_archived = 1). Never hard-deletes."""
    existing = get_product(conn, product_id)
    if existing is None:
        return fail(ProductNotFoundError(product_id=product_id))
    conn.execute(
        "UPDATE products SET is_archived = 1, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
        (product_id,),
    )
    conn.commit()
    return ok(None)


def get_product(conn: sqlite3.Connection, product_id: int) -> Product | None:
    """Return a single product by id, or ``None`` if not found."""
    row = conn.execute(
        """
        SELECT p.*, c.name AS category_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.id = ?
        """,
        (product_id,),
    ).fetchone()
    return _row_to_product(row) if row is not None else None


def list_products(
    conn: sqlite3.Connection,
    *,
    search: str | None = None,
    category_id: int | None = None,
    include_archived: bool = False,
    sort_by: str | None = "name",
    sort_dir: str = "asc",
) -> list[Product]:
    """List products with optional search, category filter, and sorting.

    Archived products are excluded by default; pass ``include_archived=True``
    to include them.
    """
    column, direction = _validate_sort(sort_by, sort_dir)
    clauses: list[str] = []
    params: list[object] = []
    if not include_archived:
        clauses.append("p.is_archived = 0")
    if category_id is not None:
        clauses.append("p.category_id = ?")
        params.append(category_id)
    if search and search.strip():
        clauses.append("(p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ?)")
        like = f"%{search.strip()}%"
        params.extend([like, like, like])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT p.*, c.name AS category_name "
        "FROM products p "
        "LEFT JOIN categories c ON c.id = p.category_id "
        f"{where} ORDER BY {column} {direction.upper()}, p.id ASC"
    )
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_product(r) for r in rows]


def list_low_stock(conn: sqlite3.Connection, *, include_archived: bool = False) -> list[Product]:
    """Return non-archived products whose quantity is at or below min_stock."""
    rows = conn.execute(
        """
        SELECT p.*, c.name AS category_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.quantity <= p.min_stock
        """ + ("" if include_archived else " AND p.is_archived = 0") +
        " ORDER BY (p.quantity - p.min_stock) ASC, p.name ASC"
    ).fetchall()
    return [_row_to_product(r) for r in rows]


def list_categories(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Return active categories as ``(id, name)`` for filter/combobox use."""
    rows = conn.execute(
        "SELECT id, name FROM categories WHERE is_archived = 0 ORDER BY name ASC"
    ).fetchall()
    return [(int(r["id"]), r["name"]) for r in rows]


__all__ = [
    "ServiceError",
    "ValidationError",
    "DuplicateSKUError",
    "DuplicateBarcodeError",
    "ProductNotFoundError",
    "Result",
    "Product",
    "create_product",
    "update_product",
    "archive_product",
    "get_product",
    "list_products",
    "list_low_stock",
    "list_categories",
    "SORT_COLUMNS",
]
