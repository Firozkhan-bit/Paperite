"""Tests for src.services.product_service (service-level, no Qt).

Each test uses a per-test temporary database (isolated via a fresh file), runs
init_db once, then exercises the service through the same ``open_connection``
the UI uses. The service commits its own writes.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    """A connection to a fresh migrated database for each test."""
    from src.database.connection import open_connection
    from src.database.schema import init_db

    db = tmp_path / "paperite_service_test.db"
    monkeypatch.setenv("PAPERITE_DB_PATH", str(db))
    init_db(str(db))
    return open_connection(str(db))


def _category(conn, name="Pens") -> int:
    cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    return int(cur.lastrowid)


# --------------------------------------------------------------------------- #
# Create / update
# --------------------------------------------------------------------------- #
def test_create_product_success(conn):
    from src.services.product_service import create_product

    result = create_product(
        conn,
        name="Reynolds Trimax Blue",
        sku="PEN-001",
        barcode="8901000000017",
        purchase_price_paise=1000,
        selling_price_paise=1500,
        quantity=50,
        min_stock=10,
        unit="piece",
        description="Blue gel pen",
    )
    assert result.is_ok, result.error
    p = result.ok
    assert p.id > 0
    assert p.name == "Reynolds Trimax Blue"
    assert p.sku == "PEN-001"
    assert p.quantity == 50
    assert p.min_stock == 10
    assert p.is_archived == 0
    assert p.archived is False


def test_update_product_success(conn):
    from src.services.product_service import create_product, update_product

    created = create_product(conn, name="Pen", quantity=5, min_stock=2)
    assert created.is_ok
    pid = created.ok.id

    res = update_product(conn, pid, name="Pen Pro", quantity=20, min_stock=5,
                         selling_price_paise=2000)
    assert res.is_ok, res.error
    updated = res.ok
    assert updated.name == "Pen Pro"
    assert updated.quantity == 20
    assert updated.min_stock == 5
    assert updated.selling_price_paise == 2000


def test_update_nonexistent_product_fails(conn):
    from src.services.product_service import ProductNotFoundError, update_product

    res = update_product(conn, 99999, name="Ghost")
    assert res.is_fail
    assert isinstance(res.error, ProductNotFoundError)


# --------------------------------------------------------------------------- #
# Duplicate SKU / barcode
# --------------------------------------------------------------------------- #
def test_duplicate_sku_rejected(conn):
    from src.services.product_service import create_product

    first = create_product(conn, name="A", sku="SKU-1")
    assert first.is_ok
    second = create_product(conn, name="B", sku="SKU-1")
    assert second.is_fail
    # ValidationError carries the field -> message map
    err = second.error
    assert "sku" in err.fields  # type: ignore[attr-defined]


def test_duplicate_barcode_rejected(conn):
    from src.services.product_service import create_product

    create_product(conn, name="A", barcode="BC-1")
    res = create_product(conn, name="B", barcode="BC-1")
    assert res.is_fail
    assert "barcode" in res.error.fields  # type: ignore[attr-defined]


def test_update_keeps_own_sku(conn):
    """Updating a product can keep its own SKU without a duplicate error."""
    from src.services.product_service import create_product, update_product

    created = create_product(conn, name="A", sku="SKU-1")
    pid = created.ok.id
    res = update_product(conn, pid, name="A2", sku="SKU-1")
    assert res.is_ok, res.error


def test_update_to_existing_sku_of_other_fails(conn):
    from src.services.product_service import create_product, update_product

    a = create_product(conn, name="A", sku="SKU-A")
    create_product(conn, name="B", sku="SKU-B")
    res = update_product(conn, a.ok.id, name="A", sku="SKU-B")
    assert res.is_fail
    assert "sku" in res.error.fields  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Negative / invalid value rejection
# --------------------------------------------------------------------------- #
def test_negative_quantity_rejected(conn):
    from src.services.product_service import create_product

    res = create_product(conn, name="X", quantity=-1)
    assert res.is_fail
    assert "quantity" in res.error.fields  # type: ignore[attr-defined]


def test_negative_purchase_price_rejected(conn):
    from src.services.product_service import create_product

    res = create_product(conn, name="X", purchase_price_paise=-5)
    assert res.is_fail
    assert "purchase_price" in res.error.fields  # type: ignore[attr-defined]


def test_negative_selling_price_rejected(conn):
    from src.services.product_service import create_product

    res = create_product(conn, name="X", selling_price_paise=-1)
    assert res.is_fail
    assert "selling_price" in res.error.fields  # type: ignore[attr-defined]


def test_negative_min_stock_rejected(conn):
    from src.services.product_service import create_product

    res = create_product(conn, name="X", min_stock=-1)
    assert res.is_fail
    assert "min_stock" in res.error.fields  # type: ignore[attr-defined]


def test_empty_name_rejected(conn):
    from src.services.product_service import create_product

    res = create_product(conn, name="   ")
    assert res.is_fail
    assert "name" in res.error.fields  # type: ignore[attr-defined]


def test_create_with_nonexistent_category_fails(conn):
    from src.services.product_service import create_product

    res = create_product(conn, name="X", category_id=99999)
    assert res.is_fail
    assert "category" in res.error.fields  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Search / filter / sort / archive / low-stock
# --------------------------------------------------------------------------- #
def test_search_by_name(conn):
    from src.services.product_service import create_product, list_products

    create_product(conn, name="Reynolds Trimax Blue", sku="A1")
    create_product(conn, name="Pilot G2", sku="B2")
    res = list_products(conn, search="trimax")
    assert len(res) == 1
    assert res[0].name == "Reynolds Trimax Blue"


def test_search_by_sku(conn):
    from src.services.product_service import create_product, list_products

    create_product(conn, name="Alpha", sku="UNIQ-SKU-99")
    res = list_products(conn, search="UNIQ")
    assert len(res) == 1
    assert res[0].sku == "UNIQ-SKU-99"


def test_filter_by_category(conn):
    from src.services.product_service import create_product, list_products

    cid_a = _category(conn, "Pens")
    cid_b = _category(conn, "Notebooks")
    create_product(conn, name="Pen", category_id=cid_a)
    create_product(conn, name="Book", category_id=cid_b)
    res = list_products(conn, category_id=cid_a)
    assert len(res) == 1
    assert res[0].name == "Pen"
    assert res[0].category_name == "Pens"


def test_archived_excluded_from_default_list(conn):
    from src.services.product_service import (
        archive_product,
        create_product,
        list_products,
    )

    p = create_product(conn, name="ArchiveMe").ok
    assert len(list_products(conn)) == 1
    archive_product(conn, p.id)
    assert len(list_products(conn)) == 0, "archived should be excluded by default"
    assert len(list_products(conn, include_archived=True)) == 1


def test_archive_is_soft_delete(conn):
    from src.services.product_service import archive_product, get_product

    from src.services.product_service import create_product
    p = create_product(conn, name="Keep").ok
    res = archive_product(conn, p.id)
    assert res.is_ok
    still = get_product(conn, p.id)
    assert still is not None
    assert still.archived is True


def test_archive_nonexistent_fails(conn):
    from src.services.product_service import ProductNotFoundError, archive_product

    res = archive_product(conn, 99999)
    assert res.is_fail
    assert isinstance(res.error, ProductNotFoundError)


def test_sort_by_quantity_desc(conn):
    from src.services.product_service import create_product, list_products

    create_product(conn, name="Few", quantity=2, min_stock=0)
    create_product(conn, name="Many", quantity=100, min_stock=0)
    create_product(conn, name="Mid", quantity=20, min_stock=0)
    res = list_products(conn, sort_by="quantity", sort_dir="desc")
    assert [p.name for p in res] == ["Many", "Mid", "Few"]


def test_sort_by_name_asc_default(conn):
    from src.services.product_service import create_product, list_products

    create_product(conn, name="Charlie")
    create_product(conn, name="Alpha")
    create_product(conn, name="Bravo")
    res = list_products(conn)  # default sort: name asc
    assert [p.name for p in res] == ["Alpha", "Bravo", "Charlie"]


def test_low_stock(conn):
    from src.services.product_service import create_product, list_low_stock

    create_product(conn, name="Full", quantity=50, min_stock=10)
    create_product(conn, name="Low", quantity=5, min_stock=10)
    create_product(conn, name="Edge", quantity=10, min_stock=10)  # at threshold
    res = list_low_stock(conn)
    names = {p.name for p in res}
    assert names == {"Low", "Edge"}


def test_low_stock_excludes_archived(conn):
    from src.services.product_service import (
        archive_product,
        create_product,
        list_low_stock,
    )

    p = create_product(conn, name="ArchivedLow", quantity=0, min_stock=5).ok
    archive_product(conn, p.id)
    res = list_low_stock(conn)
    assert p.id not in {x.id for x in res}


def test_get_product_none_when_missing(conn):
    from src.services.product_service import get_product

    assert get_product(conn, 99999) is None


def test_list_categories(conn):
    from src.services.product_service import list_categories

    cid_zebra = _category(conn, "Zebra")
    cid_alpha = _category(conn, "Alpha")
    cats = list_categories(conn)
    # Ordered by name ascending.
    assert cats == [(cid_alpha, "Alpha"), (cid_zebra, "Zebra")]
