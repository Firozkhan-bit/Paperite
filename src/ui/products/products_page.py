"""Products page.

The full Products listing: a search box, category filter, sortable table, an
"Add Product" button, a "Show archived" toggle, and per-row Edit/Archive
actions. The page opens a short-lived DB connection for each data operation
(rather than holding one open for the app lifetime) so concurrency and error
isolation stay simple.

All styling flows from the design system; the page never writes inline
``setStyleSheet``. Money is displayed via :func:`src.utils.money.format_paise`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.database.connection import open_connection
from src.services import product_service as svc
from src.ui.theme import (
    CheckBox,
    ComboBox,
    InputField,
    PageHeader,
    PrimaryButton,
    SecondaryButton,
    SPACE,
    Table,
)
from src.ui.products.product_dialog import ProductDialog
from src.utils.money import format_paise

if TYPE_CHECKING:
    from src.services.product_service import Product


# Columns: (display header, sort key, width)
COLUMNS = [
    ("Name", "name", 220),
    ("SKU", "sku", 120),
    ("Category", "category", 140),
    ("Qty", "quantity", 70),
    ("Min", "min_stock", 70),
    ("Selling price", "selling_price", 110),
    ("Status", None, 110),
]


class ProductsPage(QWidget):
    """The Products page content widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._include_archived = False
        self._search_text = ""
        self._category_id: int | None = None
        self._sort_by = "name"
        self._sort_dir = "asc"
        self._products: list[Product] = []
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE[4], SPACE[4], SPACE[4], SPACE[4])
        root.setSpacing(SPACE[3])

        self.header = PageHeader("Products", "Manage your stationery catalogue")
        self.add_button = PrimaryButton("Add Product")
        self.header.add_action(self.add_button)
        root.addWidget(self.header)

        # Toolbar: search + category filter + show-archived toggle
        toolbar = QHBoxLayout()
        toolbar.setSpacing(SPACE[2])
        self.search_input = InputField(placeholder="Search by name, SKU, or barcode…")
        self.search_input.setMinimumWidth(260)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input, 1)

        self.category_combo = ComboBox()
        self.category_combo.setMinimumWidth(180)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        toolbar.addWidget(self.category_combo)

        self.show_archived_check = CheckBox("Show archived")
        self.show_archived_check.toggled.connect(self._on_show_archived_toggled)
        toolbar.addWidget(self.show_archived_check)
        toolbar.addStretch(0)
        root.addLayout(toolbar)

        # Table
        self.table = Table()
        self.table.setColumnCount(len(COLUMNS))
        headers = [c[0] for c in COLUMNS]
        self.table.setHorizontalHeaderLabels(headers)
        for i, (_, _, width) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, width)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header_view.setStretchLastSection(True)
        header_view.sectionClicked.connect(self._on_header_clicked)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self.table, 1)

        # Footer actions
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.edit_button = SecondaryButton("Edit")
        self.archive_button = SecondaryButton("Archive")
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.archive_button.clicked.connect(self._on_archive_clicked)
        footer.addWidget(self.edit_button)
        footer.addWidget(self.archive_button)
        root.addLayout(footer)

        self.add_button.clicked.connect(self._on_add_clicked)

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        """Reload categories (filter) and the products table."""
        self._reload_categories()
        self._reload_products()

    def _reload_categories(self) -> None:
        prev_id = self._category_id
        try:
            conn = open_connection()
        except Exception as exc:  # noqa: BLE001
            self._show_db_error(str(exc))
            return
        try:
            cats = svc.list_categories(conn)
        finally:
            conn.close()

        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("All categories", None)
        for cid, cname in cats:
            self.category_combo.addItem(cname, cid)
        # restore selection
        idx = 0
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == prev_id:
                idx = i
                break
        self.category_combo.setCurrentIndex(idx)
        self._category_id = self.category_combo.currentData()
        self.category_combo.blockSignals(False)

    def _reload_products(self) -> None:
        try:
            conn = open_connection()
        except Exception as exc:  # noqa: BLE001
            self._show_db_error(str(exc))
            return
        try:
            self._products = svc.list_products(
                conn,
                search=self._search_text or None,
                category_id=self._category_id,
                include_archived=self._include_archived,
                sort_by=self._sort_by,
                sort_dir=self._sort_dir,
            )
        except Exception as exc:  # noqa: BLE001
            self._show_db_error(str(exc))
            return
        finally:
            conn.close()

        self.table.setRowCount(0)
        self.table.setRowCount(len(self._products))
        for row, p in enumerate(self._products):
            self._set_item(row, 0, p.name)
            self._set_item(row, 1, p.sku or "—")
            self._set_item(row, 2, p.category_name or "—")
            qty_item = QTableWidgetItem(str(p.quantity))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, qty_item)
            min_item = QTableWidgetItem(str(p.min_stock))
            min_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, min_item)
            self._set_item(row, 5, format_paise(p.selling_price_paise))
            status = self._status_text(p)
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, status_item)
            # stash the product id in the first column item for retrieval
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

    def _set_item(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        self.table.setItem(row, col, item)

    @staticmethod
    def _status_text(p: Product) -> str:
        if p.archived:
            return "Archived"
        if p.low_stock:
            return "Low stock"
        return "In stock"

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self._reload_products()

    def _on_category_changed(self, _index: int) -> None:
        self._category_id = self.category_combo.currentData()
        self._reload_products()

    def _on_show_archived_toggled(self, checked: bool) -> None:
        self._include_archived = checked
        self._reload_products()

    def _on_header_clicked(self, logical_index: int) -> None:
        sort_key = COLUMNS[logical_index][1]
        if sort_key is None:
            return  # Status column not sortable
        if self._sort_by == sort_key:
            self._sort_dir = "desc" if self._sort_dir == "asc" else "asc"
        else:
            self._sort_by = sort_key
            self._sort_dir = "asc"
        self._reload_products()

    def _on_add_clicked(self) -> None:
        cats = self._current_categories()
        conn = self._open_or_error()
        if conn is None:
            return
        try:
            dialog = ProductDialog(conn, cats, product=None, parent=self)
            if dialog.exec():
                self._reload_products()
        finally:
            conn.close()

    def _on_edit_clicked(self) -> None:
        pid = self._selected_product_id()
        if pid is None:
            return
        conn = self._open_or_error()
        if conn is None:
            return
        try:
            product = svc.get_product(conn, pid)
            if product is None:
                QMessageBox.warning(self, "Not found", "That product no longer exists.")
                return
            dialog = ProductDialog(conn, self._current_categories(), product=product, parent=self)
            if dialog.exec():
                self._reload_products()
        finally:
            conn.close()

    def _on_double_click(self, item: QTableWidgetItem) -> None:
        self._on_edit_clicked()

    def _on_archive_clicked(self) -> None:
        pid = self._selected_product_id()
        if pid is None:
            return
        confirm = QMessageBox.question(
            self,
            "Archive product",
            "Archive this product? It will be hidden from the default list but kept for history.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        conn = self._open_or_error()
        if conn is None:
            return
        try:
            result = svc.archive_product(conn, pid)
            if result.is_fail:
                QMessageBox.warning(self, "Could not archive", str(result.error))
            else:
                self._reload_products()
        finally:
            conn.close()

    def _on_context_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu

        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        pid = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        act_edit = menu.addAction("Edit…")
        act_archive = menu.addAction("Archive")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self._edit_by_id(pid)
        elif chosen == act_archive:
            self._archive_by_id(pid)

    # ------------------------------------------------------------------ #
    # Small helpers
    # ------------------------------------------------------------------ #
    def _selected_product_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _edit_by_id(self, pid: int | None) -> None:
        if pid is None:
            return
        conn = self._open_or_error()
        if conn is None:
            return
        try:
            product = svc.get_product(conn, pid)
            if product is None:
                return
            if ProductDialog(conn, self._current_categories(), product=product, parent=self).exec():
                self._reload_products()
        finally:
            conn.close()

    def _archive_by_id(self, pid: int | None) -> None:
        if pid is None:
            return
        conn = self._open_or_error()
        if conn is None:
            return
        try:
            svc.archive_product(conn, pid)
            self._reload_products()
        finally:
            conn.close()

    def _current_categories(self) -> list[tuple[int, str]]:
        conn = self._open_or_error()
        if conn is None:
            return []
        try:
            return svc.list_categories(conn)
        finally:
            conn.close()

    def _open_or_error(self):
        try:
            return open_connection()
        except Exception as exc:  # noqa: BLE001
            self._show_db_error(str(exc))
            return None

    def _show_db_error(self, message: str) -> None:
        QMessageBox.critical(
            self,
            "Database error",
            "Paperite could not open its database.\n\n" + message,
        )
