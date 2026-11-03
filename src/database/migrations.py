"""Versioned database migrations for Paperite.

Strategy
--------

A single bookkeeping table ``schema_version`` stores exactly one row (id=1)
holding the highest migration version applied to the database.

Each migration is a small, pure-Python callable registered in
:data:`MIGRATIONS`, keyed by its integer version (1, 2, 3, ...). The
:func:`run_migrations` runner:

1. Ensures the ``schema_version`` table exists.
2. Reads the current version (0 for a brand-new database).
3. Applies every migration whose version is greater than the current one, in
   ascending order, each inside its own transaction.
4. Updates ``schema_version`` after each successful migration.
5. Is idempotent: running it on an already-up-to-date database is a no-op
   that does not error and leaves the version unchanged.

Because v1 creates the *initial* schema (all Phase 3 tables) and the runner
itself bootstraps the ``schema_version`` table, a fresh database reaches
version 1 after the first run, and an existing v1 database stays at 1 on a
second run.

Adding a future migration
-------------------------

To add migration N:

1. Write a ``_migrate_vN(conn)`` function performing the schema change.
   - DDL only, or data backfill, as needed.
   - Operate on the open ``conn``; the runner wraps the call in a
     transaction, so do not start a separate one for the same connection.
2. Register it in :data:`MIGRATIONS` under key ``N``.
3. Bump nothing else -- the runner picks it up automatically.

Version numbers must be strictly increasing contiguous integers starting
at 1; never reuse or renumber an already-shipped migration.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

MigrationFn = Callable[[sqlite3.Connection], None]

SCHEMA_VERSION_TABLE = "schema_version"


# ---------------------------------------------------------------------------
# v1: initial schema (Phase 3)
# ---------------------------------------------------------------------------
def _migrate_v1(conn: sqlite3.Connection) -> None:
    """Create the initial Paperite schema (Phase 3 tables).

    Money is stored as INTEGER paise (1 rupee = 100 paise); quantities are
    whole numbers. Constraints enforced here:

    - ``products.purchase_price_paise`` / ``selling_price_paise`` >= 0
    - ``products.quantity`` / ``min_stock`` >= 0
    - ``purchase_items.quantity`` > 0, ``unit_cost_paise`` >= 0
    - ``sale_items.quantity`` > 0
    - ``purchases.status`` IN ('draft','received','cancelled')
    - ``sales.payment_method`` IN ('cash','upi','card','other')
    - ``sales.status`` IN ('completed','cancelled')
    - ``stock_movements.reason`` IN
      ('opening','purchase','sale','damaged','lost','return','correction')
    - UNIQUE on ``categories.name``, ``products.sku``, ``products.barcode``,
      ``sales.invoice_no``.
    - FKs from products/purchase_items/sale_items/stock_movements/purchases.

    Statements are applied one at a time via :meth:`execute` (NOT
    :meth:`executescript`) so they participate in the migration runner's
    transaction; ``executescript`` issues an implicit COMMIT that would break
    the runner's rollback semantics.
    """
    for stmt in _V1_STATEMENTS:
        conn.execute(stmt)


_V1_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS categories (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL UNIQUE,
        is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
        created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        name                  TEXT    NOT NULL,
        sku                   TEXT    UNIQUE,
        barcode               TEXT    UNIQUE,
        category_id           INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        purchase_price_paise  INTEGER NOT NULL CHECK (purchase_price_paise >= 0),
        selling_price_paise   INTEGER NOT NULL CHECK (selling_price_paise  >= 0),
        quantity              INTEGER NOT NULL CHECK (quantity      >= 0),
        min_stock             INTEGER NOT NULL CHECK (min_stock     >= 0),
        unit                  TEXT,
        description           TEXT,
        is_archived           INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
        created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
        updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS suppliers (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT    NOT NULL,
        contact_person TEXT,
        phone         TEXT,
        email         TEXT,
        address       TEXT,
        notes         TEXT,
        is_archived   INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
        created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS purchases (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id    INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
        purchase_date  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
        status         TEXT    NOT NULL DEFAULT 'draft'
                               CHECK (status IN ('draft','received','cancelled')),
        discount_paise  INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0),
        notes          TEXT,
        created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS purchase_items (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id       INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
        product_id        INTEGER NOT NULL REFERENCES products(id)  ON DELETE RESTRICT,
        quantity          INTEGER NOT NULL CHECK (quantity > 0),
        unit_cost_paise    INTEGER NOT NULL CHECK (unit_cost_paise >= 0),
        line_total_paise  INTEGER NOT NULL CHECK (line_total_paise >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sales (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no      TEXT    NOT NULL UNIQUE,
        sale_date       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
        payment_method  TEXT    NOT NULL DEFAULT 'cash'
                                CHECK (payment_method IN ('cash','upi','card','other')),
        discount_paise   INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0),
        status          TEXT    NOT NULL DEFAULT 'completed'
                                CHECK (status IN ('completed','cancelled')),
        cancel_reason   TEXT,
        created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sale_items (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id                 INTEGER NOT NULL REFERENCES sales(id)    ON DELETE CASCADE,
        product_id              INTEGER NOT NULL REFERENCES products(id)  ON DELETE RESTRICT,
        quantity                INTEGER NOT NULL CHECK (quantity > 0),
        unit_price_paise        INTEGER NOT NULL CHECK (unit_price_paise >= 0),
        unit_cost_snapshot_paise INTEGER NOT NULL CHECK (unit_cost_snapshot_paise >= 0),
        line_total_paise        INTEGER NOT NULL CHECK (line_total_paise >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_movements (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id     INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        change         INTEGER NOT NULL,
        reason         TEXT    NOT NULL
                               CHECK (reason IN
                                 ('opening','purchase','sale','damaged',
                                  'lost','return','correction')),
        reference_type TEXT,
        reference_id   INTEGER,
        note           TEXT,
        created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )
    """,
]


# ---------------------------------------------------------------------------
# Migration registry (ordered by version).
# ---------------------------------------------------------------------------
MIGRATIONS: dict[int, MigrationFn] = {
    1: _migrate_v1,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def _ensure_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} (
            id      INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        )
        """
    )


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        f"SELECT version FROM {SCHEMA_VERSION_TABLE} WHERE id = 1"
    ).fetchone()
    return int(row["version"]) if row is not None else 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        f"""
        INSERT INTO {SCHEMA_VERSION_TABLE} (id, version) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET version = excluded.version
        """,
        (version,),
    )


def run_migrations(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations to ``conn`` and return the new version.

    Idempotent: if the database is already up to date, this is a no-op and
    returns the current version unchanged. Each migration runs inside its own
    transaction; on failure the transaction is rolled back and the exception
    propagates (the database remains at its pre-migration version).
    """
    _ensure_version_table(conn)
    # Commit the bookkeeping table creation so it persists even if a later
    # migration is skipped (idempotent no-op) or fails.
    conn.commit()
    current = _current_version(conn)

    for version in sorted(MIGRATIONS):
        if version <= current:
            continue
        fn = MIGRATIONS[version]
        try:
            fn(conn)
            _set_version(conn, version)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        current = version

    return current
