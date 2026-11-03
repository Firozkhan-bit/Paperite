"""Phase 3: SQLite database foundation tests.

Each test uses a per-test temporary database file via the ``PAPERITE_DB_PATH``
environment variable, so the user's real app-data database is never touched.
The tests are pure sqlite3 / stdlib: they never import PySide6, so they run on
any host (including this headless sandbox).
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# Tables that the v1 schema must create (excluding the bookkeeping table).
PHASE3_TABLES = [
    "categories",
    "products",
    "suppliers",
    "purchases",
    "purchase_items",
    "sales",
    "sale_items",
    "stock_movements",
]


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a fresh temp database path, isolating each test from real data."""
    db = tmp_path / "paperite_test.db"
    return db


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection the same way the app does (FKs ON, Row factory)."""
    from src.database.connection import open_connection

    return open_connection(str(db_path))


def _init(db_path: Path) -> int:
    from src.database.schema import init_db

    return init_db(str(db_path))


# --------------------------------------------------------------------------- #
# Schema creation
# --------------------------------------------------------------------------- #
def test_init_creates_all_tables(tmp_db: Path):
    """init_db creates every Phase 3 table plus the schema_version table."""
    version = _init(tmp_db)
    assert version == 1

    conn = _connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r["name"] for r in rows}
    finally:
        conn.close()

    for table in PHASE3_TABLES:
        assert table in names, f"missing table: {table}"
    assert "schema_version" in names


def test_schema_version_table_records_version(tmp_db: Path):
    """The schema_version table holds version=1 after init."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        row = conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["version"] == 1


def test_foreign_keys_enforced(tmp_db: Path):
    """PRAGMA foreign_keys = ON: inserting a child with a bogus parent fails."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        # products.category_id -> categories.id; category 999 does not exist.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO products (name, purchase_price_paise, "
                "selling_price_paise, quantity, min_stock, category_id) "
                "VALUES ('X', 0, 0, 0, 0, 999)"
            )
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Migration runner idempotency
# --------------------------------------------------------------------------- #
def test_runner_is_idempotent(tmp_db: Path):
    """Running run_migrations twice does not error and the version is stable."""
    from src.database.migrations import run_migrations

    _init(tmp_db)

    conn = _connect(tmp_db)
    try:
        v1 = run_migrations(conn)
        v2 = run_migrations(conn)
    finally:
        conn.close()

    assert v1 == 1
    assert v2 == 1


def test_init_db_idempotent(tmp_db: Path):
    """Calling init_db twice succeeds and leaves the version at 1."""
    assert _init(tmp_db) == 1
    assert _init(tmp_db) == 1


# --------------------------------------------------------------------------- #
# CHECK / UNIQUE constraints
# --------------------------------------------------------------------------- #
def test_negative_quantity_rejected(tmp_db: Path):
    """products.quantity has CHECK (quantity >= 0); a negative value fails."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO products (name, purchase_price_paise, "
                "selling_price_paise, quantity, min_stock) "
                "VALUES ('Bad', 0, 0, -1, 0)"
            )
    finally:
        conn.close()


def test_negative_price_rejected(tmp_db: Path):
    """products.purchase_price_paise has CHECK (>= 0); negative fails."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO products (name, purchase_price_paise, "
                "selling_price_paise, quantity, min_stock) "
                "VALUES ('Bad', -5, 0, 0, 0)"
            )
    finally:
        conn.close()


def test_duplicate_sku_rejected(tmp_db: Path):
    """products.sku is UNIQUE; inserting the same sku twice fails."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO products (name, sku, purchase_price_paise, "
            "selling_price_paise, quantity, min_stock) "
            "VALUES ('A', 'SKU-1', 0, 0, 0, 0)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO products (name, sku, purchase_price_paise, "
                "selling_price_paise, quantity, min_stock) "
                "VALUES ('B', 'SKU-1', 0, 0, 0, 0)"
            )
    finally:
        conn.close()


def test_null_sku_allowed_multiple(tmp_db: Path):
    """products.sku is UNIQUE but nullable: multiple NULL skus are allowed."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO products (name, sku, purchase_price_paise, "
            "selling_price_paise, quantity, min_stock) "
            "VALUES ('A', NULL, 0, 0, 0, 0)"
        )
        conn.execute(
            "INSERT INTO products (name, sku, purchase_price_paise, "
            "selling_price_paise, quantity, min_stock) "
            "VALUES ('B', NULL, 0, 0, 0, 0)"
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    finally:
        conn.close()
    assert count == 2


def test_purchase_item_quantity_must_be_positive(tmp_db: Path):
    """purchase_items.quantity has CHECK (quantity > 0); zero fails."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        cur = conn.execute(
            "INSERT INTO products (name, purchase_price_paise, "
            "selling_price_paise, quantity, min_stock) "
            "VALUES ('P', 100, 150, 10, 2)"
        )
        product_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO suppliers (name) VALUES ('S')"
        )
        supplier_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO purchases (supplier_id, status) VALUES (?, 'draft')",
            (supplier_id,),
        )
        purchase_id = cur.lastrowid
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO purchase_items (purchase_id, product_id, "
                "quantity, unit_cost_paise, line_total_paise) "
                "VALUES (?, ?, 0, 0, 0)",
                (purchase_id, product_id),
            )
    finally:
        conn.close()


def test_invalid_purchase_status_rejected(tmp_db: Path):
    """purchases.status CHECK rejects values outside the allowed set."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO purchases (status) VALUES ('bogus')"
            )
    finally:
        conn.close()


def test_invalid_sale_payment_method_rejected(tmp_db: Path):
    """sales.payment_method CHECK rejects values outside the allowed set."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sales (invoice_no, payment_method) "
                "VALUES ('INV-1', 'bitcoin')"
            )
    finally:
        conn.close()


def test_duplicate_invoice_no_rejected(tmp_db: Path):
    """sales.invoice_no is UNIQUE."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO sales (invoice_no, payment_method, status) "
            "VALUES ('INV-1', 'cash', 'completed')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sales (invoice_no, payment_method, status) "
                "VALUES ('INV-1', 'upi', 'completed')"
            )
    finally:
        conn.close()


def test_stock_movement_reason_check(tmp_db: Path):
    """stock_movements.reason CHECK rejects unknown reasons."""
    _init(tmp_db)
    conn = _connect(tmp_db)
    try:
        cur = conn.execute(
            "INSERT INTO products (name, purchase_price_paise, "
            "selling_price_paise, quantity, min_stock) "
            "VALUES ('P', 0, 0, 0, 0)"
        )
        product_id = cur.lastrowid
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO stock_movements (product_id, change, reason) "
                "VALUES (?, 5, 'teleported')",
                (product_id,),
            )
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Path resolution / connection configuration
# --------------------------------------------------------------------------- #
def test_env_var_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """PAPERITE_DB_PATH overrides the platform-default path."""
    from src.database.connection import resolve_db_path

    custom = tmp_path / "custom.db"
    monkeypatch.setenv("PAPERITE_DB_PATH", str(custom))
    assert resolve_db_path() == custom


def test_explicit_path_wins_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An explicit path argument beats the env var."""
    from src.database.connection import resolve_db_path

    env_path = tmp_path / "env.db"
    arg_path = tmp_path / "arg.db"
    monkeypatch.setenv("PAPERITE_DB_PATH", str(env_path))
    assert resolve_db_path(str(arg_path)) == arg_path


def test_connection_has_foreign_keys_and_row_factory(tmp_db: Path):
    """open_connection enables foreign_keys and uses sqlite3.Row."""
    from src.database.connection import open_connection

    _init(tmp_db)
    conn = open_connection(str(tmp_db))
    try:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1  # ON
        # Row factory: access a column by name.
        row = conn.execute("SELECT 1 AS one").fetchone()
        assert row["one"] == 1
    finally:
        conn.close()
