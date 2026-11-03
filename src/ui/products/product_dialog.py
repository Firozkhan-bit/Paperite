"""Add/Edit Product dialog.

A modal :class:`QDialog` collecting all blueprint product fields with inline
validation. The dialog owns no business logic: it collects field values,
calls :mod:`src.services.product_service`, and maps the returned typed errors
to inline field-error messages. The dialog never raises and never shows a raw
DB traceback.

Money fields are entered as rupee strings and converted to integer paise via
:mod:`src.utils.money` so no floats are ever stored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services import product_service as svc
from src.ui.theme import (
    ComboBox,
    Field,
    InputField,
    IntSpinBox,
    PrimaryButton,
    SecondaryButton,
    SPACE,
)
from src.utils.money import format_paise, parse_paise_or_none

if TYPE_CHECKING:
    import sqlite3
    from src.services.product_service import Product


class ProductDialog(QDialog):
    """Add or edit a single product.

    Parameters
    ----------
    conn:
        The SQLite connection to use (the service commits its own writes).
    categories:
        Sequence of ``(id, name)`` for the category dropdown.
    product:
        Existing product to edit, or ``None`` to create a new one.
    parent:
        Optional parent widget.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        categories: list[tuple[int, str]],
        product: Product | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._product = product
        self._categories = categories
        self._category_ids: list[int | None] = []  # parallel to combo items

        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setModal(True)
        self.setMinimumWidth(460)

        self._build_ui()
        if product is not None:
            self._load(product)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE[4], SPACE[4], SPACE[4], SPACE[4])
        root.setSpacing(SPACE[3])

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(SPACE[3])
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Name
        self.name_input = InputField(placeholder="e.g. Reynolds Trimax Blue")
        self.name_field = Field("Name", self.name_input)
        form.addRow(self.name_field)

        # SKU + Barcode (side by side)
        sku_barcode_row = QWidget()
        sb_layout = QHBoxLayout(sku_barcode_row)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(SPACE[3])
        self.sku_input = InputField(placeholder="Optional, unique")
        self.barcode_input = InputField(placeholder="Optional, unique")
        self.sku_field = Field("SKU", self.sku_input)
        self.barcode_field = Field("Barcode", self.barcode_input)
        sb_layout.addWidget(self.sku_field)
        sb_layout.addWidget(self.barcode_field)
        form.addRow(sku_barcode_row)

        # Category
        self.category_combo = ComboBox()
        self.category_combo.addItem("— None —", None)
        self._category_ids.append(None)
        for cid, cname in self._categories:
            self.category_combo.addItem(cname, cid)
            self._category_ids.append(cid)
        self.category_field = Field("Category", self.category_combo)
        form.addRow(self.category_field)

        # Prices (side by side)
        prices_row = QWidget()
        pr_layout = QHBoxLayout(prices_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(SPACE[3])
        self.purchase_price_input = InputField(placeholder="₹0.00")
        self.selling_price_input = InputField(placeholder="₹0.00")
        self.purchase_price_field = Field("Purchase price", self.purchase_price_input)
        self.selling_price_field = Field("Selling price", self.selling_price_input)
        pr_layout.addWidget(self.purchase_price_field)
        pr_layout.addWidget(self.selling_price_field)
        form.addRow(prices_row)

        # Quantity + Min stock (side by side)
        qty_row = QWidget()
        q_layout = QHBoxLayout(qty_row)
        q_layout.setContentsMargins(0, 0, 0, 0)
        q_layout.setSpacing(SPACE[3])
        self.quantity_input = IntSpinBox(minimum=0)
        self.min_stock_input = IntSpinBox(minimum=0)
        self.quantity_input.setValue(0)
        self.min_stock_input.setValue(0)
        self.quantity_field = Field("Quantity", self.quantity_input)
        self.min_stock_field = Field("Min stock", self.min_stock_input)
        q_layout.addWidget(self.quantity_field)
        q_layout.addWidget(self.min_stock_field)
        form.addRow(qty_row)

        # Unit
        self.unit_input = InputField(placeholder="e.g. piece, box, dozen")
        self.unit_field = Field("Unit", self.unit_input)
        form.addRow(self.unit_field)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setObjectName("inputField")
        self.description_input.setPlaceholderText("Optional notes about this product")
        self.description_input.setFixedHeight(80)
        self.description_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.description_field = Field("Description", self.description_input)
        form.addRow(self.description_field)

        root.addWidget(form_host)
        root.addStretch(1)

        # Buttons (custom so they use the design system; reject on Escape).
        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        self.cancel_button = SecondaryButton("Cancel")
        self.save_button = PrimaryButton("Save")
        buttons_row.addWidget(self.cancel_button)
        buttons_row.addWidget(self.save_button)
        root.addLayout(buttons_row)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._on_save)

    # ------------------------------------------------------------------ #
    # Loading an existing product
    # ------------------------------------------------------------------ #
    def _load(self, p: Product) -> None:
        self.name_input.setText(p.name)
        self.sku_input.setText(p.sku or "")
        self.barcode_input.setText(p.barcode or "")
        # category combo
        idx = 0
        if p.category_id is not None:
            for i, cid in enumerate(self._category_ids):
                if cid == p.category_id:
                    idx = i
                    break
        self.category_combo.setCurrentIndex(idx)
        self.purchase_price_input.setText(format_paise(p.purchase_price_paise))
        self.selling_price_input.setText(format_paise(p.selling_price_paise))
        self.quantity_input.setValue(p.quantity)
        self.min_stock_input.setValue(p.min_stock)
        self.unit_input.setText(p.unit or "")
        self.description_input.setPlainText(p.description or "")

    # ------------------------------------------------------------------ #
    # Validation + save
    # ------------------------------------------------------------------ #
    def _clear_errors(self) -> None:
        for field in (
            self.name_field, self.sku_field, self.barcode_field,
            self.category_field, self.purchase_price_field, self.selling_price_field,
            self.quantity_field, self.min_stock_field, self.unit_field,
            self.description_field,
        ):
            field.set_error(None)

    def _on_save(self) -> None:
        self._clear_errors()
        name = self.name_input.text()
        sku = self.sku_input.text() or None
        barcode = self.barcode_input.text() or None
        unit = self.unit_input.text() or None
        description = self.description_input.toPlainText() or None
        pp_raw = self.purchase_price_input.text().strip()
        sp_raw = self.selling_price_input.text().strip()
        try:
            purchase_price = parse_paise_or_none(pp_raw) or 0
        except ValueError:
            self.purchase_price_field.set_error("Enter a valid amount, e.g. ₹12.50")
            return
        try:
            selling_price = parse_paise_or_none(sp_raw) or 0
        except ValueError:
            self.selling_price_field.set_error("Enter a valid amount, e.g. ₹12.50")
            return
        if not name.strip():
            self.name_field.set_error("Name is required.")
            return

        quantity = self.quantity_input.value()
        min_stock = self.min_stock_input.value()
        category_id = self._category_ids[self.category_combo.currentIndex()]

        common = dict(
            name=name,
            sku=sku,
            barcode=barcode,
            category_id=category_id,
            purchase_price_paise=purchase_price,
            selling_price_paise=selling_price,
            quantity=quantity,
            min_stock=min_stock,
            unit=unit,
            description=description,
        )
        if self._product is None:
            result = svc.create_product(self._conn, **common)
        else:
            result = svc.update_product(self._conn, self._product.id, **common)

        if result.is_ok:
            self._saved_product = result.ok
            self.accept()
        else:
            err = result.error
            field_map = {
                "name": self.name_field,
                "sku": self.sku_field,
                "barcode": self.barcode_field,
                "category": self.category_field,
                "purchase_price": self.purchase_price_field,
                "selling_price": self.selling_price_field,
                "quantity": self.quantity_field,
                "min_stock": self.min_stock_field,
            }
            if isinstance(err, svc.ValidationError):
                for key, msg in err.fields.items():
                    f = field_map.get(key)
                    if f is not None:
                        f.set_error(msg)
                QMessageBox.warning(self, "Could not save product",
                                     "Please fix the highlighted fields.")
            else:
                QMessageBox.warning(self, "Could not save product", str(err))

    # ------------------------------------------------------------------ #
    # Public result accessor
    # ------------------------------------------------------------------ #
    @property
    def saved_product(self) -> Product | None:
        return getattr(self, "_saved_product", None)
