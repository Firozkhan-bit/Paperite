"""Paperite design system: design tokens, QSS stylesheet, and reusable widgets.

This module is the single source of truth for the application's visual style.
Pages and dialogs must NOT scatter inline ``setStyleSheet`` calls; instead they
consume the design system by:

    1. importing the reusable widgets: ``PrimaryButton``, ``SecondaryButton``,
       ``InputField``, ``Table``, ``PageHeader``, ``SidebarNavItem``; and
    2. applying semantic ``objectName``\u2019s to plain widgets where a reusable
       class is not appropriate (e.g. ``QLabel#comingSoon``), so styling flows
       from the QSS defined here.

Tokens are plain Python constants (``COLORS``, ``TYPE``, ``SPACE``, ``RADIUS``)
and the QSS is assembled from them via ``%``-formatting (which does not clash
with QSS braces). Call :func:`apply_theme` once on the ``QApplication`` to
install the stylesheet and default font.

Palette: warm white surfaces, soft grey panels, charcoal text, muted
sage / forest green / deep teal accents. Rules: subtle 1px borders, minimal
shadows, NO gradients, NO neon, consistent 6px radius.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Colour tokens
# --------------------------------------------------------------------------- #
COLORS = {
    # Surfaces
    "bg": "#FBFAF7",            # warm white -- primary surface
    "bg_alt": "#F3F2EE",        # soft grey -- alternating panels/rows
    "sidebar": "#F7F6F1",       # sidebar surface (slightly warmer)
    # Lines
    "border": "#E4E2DA",        # subtle hairline
    "border_strong": "#D2CFC2", # inputs / hover borders
    "grid": "#ECEAE1",          # table grid
    # Text
    "text": "#2A2A28",          # charcoal -- primary text
    "text_muted": "#6B6A63",    # secondary text
    # Primary accent (forest green)
    "primary": "#44624A",
    "primary_hover": "#38513D",
    "primary_pressed": "#2C4131",
    "primary_text": "#FFFFFF",
    # Secondary accent (deep teal)
    "secondary": "#2C5F5C",
    "secondary_border": "#C4D1CF",
    "secondary_hover_bg": "#ECEFEE",
    "secondary_pressed_bg": "#DEE5E4",
    # Tertiary accent (muted sage) -- used for selection/selection backgrounds
    "accent_sage": "#8B9D83",
    "nav_hover": "#ECEBE2",
    "nav_selected_bg": "#E5E8DD",
    "selection": "#D7E0D0",
    # States
    "disabled_bg": "#CDD3C8",
    "disabled_text": "#F3F2EE",
    "danger": "#9A4A3B",
}

# --------------------------------------------------------------------------- #
# Typography tokens
# --------------------------------------------------------------------------- #
FONT_FAMILY = '"Inter", "Segoe UI", "Microsoft YaHei", "PingFang SC", "Noto Sans", sans-serif'
FONT_FAMILIES = ["Inter", "Segoe UI", "Microsoft YaHei", "PingFang SC", "Noto Sans", "sans-serif"]

# name -> (size_px, weight)
TYPE = {
    "h1": (22, 700),
    "h2": (18, 600),
    "h3": (15, 600),
    "body": (13, 400),
    "body_medium": (13, 500),
    "caption": (11, 400),
}

# --------------------------------------------------------------------------- #
# Spacing & shape tokens
# --------------------------------------------------------------------------- #
SPACE = (4, 8, 12, 16, 24)   # spacing scale
RADIUS = 6                    # consistent corner radius
RADIUS_SM = 4

# --------------------------------------------------------------------------- #
# QSS stylesheet (built from the tokens above)
# --------------------------------------------------------------------------- #
QSS = """
* { font-family: %(font)s; }

QMainWindow, QWidget#MainWindow { background-color: %(bg)s; }

/* ---- Sidebar ---- */
QFrame#sidebar {
    background-color: %(sidebar)s;
    border-right: 1px solid %(border)s;
}
QLabel#brand {
    font-size: 16px; font-weight: 700; color: %(primary)s;
    padding: 6px 20px 0 20px;
}
QLabel#brandCaption {
    font-size: 11px; font-weight: 400; color: %(text_muted)s;
    padding: 0 20px 16px 20px;
}

/* ---- Sidebar nav items ---- */
QPushButton#navItem {
    background: transparent; border: none;
    text-align: left; padding: 9px 20px;
    color: %(text_muted)s; font-weight: 500; font-size: 13px;
}
QPushButton#navItem:hover { background-color: %(nav_hover)s; color: %(text)s; }
QPushButton#navItem:checked {
    background-color: %(nav_selected_bg)s; color: %(primary)s;
    border-left: 3px solid %(primary)s; padding-left: 17px;
    font-weight: 600;
}

/* ---- Page header ---- */
QFrame#pageHeader { background: transparent; border-bottom: 1px solid %(border)s; }
QLabel#pageTitle { font-size: 18px; font-weight: 600; color: %(text)s; }
QLabel#pageSubtitle { font-size: 11px; font-weight: 400; color: %(text_muted)s; }
QLabel#comingSoon { color: %(text_muted)s; font-size: 13px; }
QFrame#placeholderBadge {
    background-color: %(nav_selected_bg)s; color: %(primary)s;
    border: 1px solid %(accent_sage)s; border-radius: 4px;
}
QLabel#badgeText { color: %(primary)s; font-size: 11px; font-weight: 600; padding: 2px 8px; }

/* ---- Buttons ---- */
QPushButton#primaryButton {
    background-color: %(primary)s; color: %(primary_text)s;
    border: 1px solid %(primary_pressed)s; border-radius: 6px;
    padding: 8px 16px; font-weight: 500; font-size: 13px;
}
QPushButton#primaryButton:hover { background-color: %(primary_hover)s; }
QPushButton#primaryButton:pressed { background-color: %(primary_pressed)s; }
QPushButton#primaryButton:disabled {
    background-color: %(disabled_bg)s; color: %(disabled_text)s;
    border-color: %(disabled_bg)s;
}

QPushButton#secondaryButton {
    background-color: %(bg)s; color: %(secondary)s;
    border: 1px solid %(secondary_border)s; border-radius: 6px;
    padding: 8px 16px; font-weight: 500; font-size: 13px;
}
QPushButton#secondaryButton:hover { background-color: %(secondary_hover_bg)s; border-color: %(secondary)s; }
QPushButton#secondaryButton:pressed { background-color: %(secondary_pressed_bg)s; }
QPushButton#secondaryButton:disabled { color: %(disabled_text)s; border-color: %(disabled_bg)s; }

/* ---- Inputs ---- */
QLineEdit#inputField, QTextEdit#inputField, QPlainTextEdit#inputField {
    background-color: #FFFFFF; border: 1px solid %(border_strong)s; border-radius: 6px;
    padding: 8px 10px; color: %(text)s; font-size: 13px;
    selection-background-color: %(selection)s;
}
QLineEdit#inputField:focus, QTextEdit#inputField:focus, QPlainTextEdit#inputField:focus {
    border-color: %(primary)s;
}
QLineEdit#inputField[error="true"], QTextEdit#inputField[error="true"],
QPlainTextEdit#inputField[error="true"], QComboBox#inputField[error="true"] {
    border-color: %(danger)s;
}
QLabel#fieldError {
    color: %(danger)s; font-size: 11px; font-weight: 400;
}
QLabel#fieldLabel {
    color: %(text)s; font-size: 12px; font-weight: 500;
}
QCheckBox#designCheckbox {
    spacing: 8px; color: %(text)s; font-size: 13px;
}
QComboBox#inputField {
    background-color: #FFFFFF; border: 1px solid %(border_strong)s; border-radius: 6px;
    padding: 6px 10px; color: %(text)s; font-size: 13px;
}
QComboBox#inputField:focus { border-color: %(primary)s; }
QComboBox QAbstractItemView {
    background-color: #FFFFFF; border: 1px solid %(border)s;
    selection-background-color: %(selection)s; selection-color: %(text)s;
}

/* ---- Table ---- */
QTableWidget, QTableView {
    background-color: #FFFFFF; alternate-background-color: %(bg_alt)s;
    border: 1px solid %(border)s; border-radius: 6px; gridline-color: %(grid)s;
    selection-background-color: %(selection)s; selection-color: %(text)s;
}
QHeaderView::section {
    background-color: %(bg_alt)s; color: %(text_muted)s;
    border: none; border-bottom: 1px solid %(border)s;
    padding: 8px 10px; font-weight: 600; font-size: 12px;
}
QTableWidget::item, QTableView::item { padding: 6px 8px; }

/* ---- Spin boxes ---- */
QSpinBox {
    background-color: #FFFFFF; border: 1px solid %(border_strong)s; border-radius: 6px;
    padding: 6px 8px; color: %(text)s; font-size: 13px;
}
QSpinBox:focus { border-color: %(primary)s; }
QSpinBox[error="true"] { border-color: %(danger)s; }
QSpinBox::up-button, QSpinBox::down-button {
    background: transparent; border: none; width: 16px;
}
QSpinBox::up-arrow { image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-bottom: 5px solid %(text_muted)s; width: 0; height: 0; }
QSpinBox::down-arrow { image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid %(text_muted)s; width: 0; height: 0; }

/* ---- Dialog ---- */
QDialog { background-color: %(bg)s; }

/* ---- Scrollbars ---- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: %(border_strong)s; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: %(text_muted)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: %(border_strong)s; border-radius: 4px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: %(text_muted)s; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
""" % {
    "font": FONT_FAMILY,
    "bg": COLORS["bg"],
    "bg_alt": COLORS["bg_alt"],
    "sidebar": COLORS["sidebar"],
    "border": COLORS["border"],
    "border_strong": COLORS["border_strong"],
    "grid": COLORS["grid"],
    "text": COLORS["text"],
    "text_muted": COLORS["text_muted"],
    "primary": COLORS["primary"],
    "primary_hover": COLORS["primary_hover"],
    "primary_pressed": COLORS["primary_pressed"],
    "primary_text": COLORS["primary_text"],
    "secondary": COLORS["secondary"],
    "secondary_border": COLORS["secondary_border"],
    "secondary_hover_bg": COLORS["secondary_hover_bg"],
    "secondary_pressed_bg": COLORS["secondary_pressed_bg"],
    "accent_sage": COLORS["accent_sage"],
    "nav_hover": COLORS["nav_hover"],
    "nav_selected_bg": COLORS["nav_selected_bg"],
    "selection": COLORS["selection"],
    "disabled_bg": COLORS["disabled_bg"],
    "disabled_text": COLORS["disabled_text"],
    "danger": COLORS["danger"],
}


def apply_theme(app) -> None:
    """Install the Paperite stylesheet and default font on a ``QApplication``.

    Call once, before any top-level window is shown.
    """
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPixelSize(TYPE["body"][0])
    app.setFont(font)
    app.setStyleSheet(QSS)


# --------------------------------------------------------------------------- #
# Reusable widgets
# --------------------------------------------------------------------------- #
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class PrimaryButton(QPushButton):
    """Primary call-to-action button (forest green)."""

    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setObjectName("primaryButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SecondaryButton(QPushButton):
    """Secondary button (outlined, deep teal)."""

    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setObjectName("secondaryButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class InputField(QLineEdit):
    """Standard text input field."""

    def __init__(self, placeholder: str = ""):
        super().__init__()
        self.setObjectName("inputField")
        if placeholder:
            self.setPlaceholderText(placeholder)


class Table(QTableWidget):
    """Standard data table with the design system defaults applied."""

    def __init__(self):
        super().__init__()
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)


class SidebarNavItem(QPushButton):
    """Checkable, exclusive sidebar navigation entry."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("navItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)


class PageHeader(QFrame):
    """Page title bar with an optional subtitle and trailing action slot.

    Use :meth:`add_action` to place primary/secondary buttons on the right.
    """

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("pageHeader")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(12)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageTitle")
        text_box.addWidget(self.title_label)
        self.subtitle_label: QLabel | None = None
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("pageSubtitle")
            text_box.addWidget(self.subtitle_label)
        outer.addLayout(text_box)
        outer.addStretch(1)

    def add_action(self, widget) -> None:
        """Append a widget (typically a button) to the header's trailing slot."""
        self.layout().addWidget(widget)


class ComboBox(QComboBox):
    """Design-system combo box. Use :meth:`set_error` to flag invalid state."""

    def __init__(self):
        super().__init__()
        self.setObjectName("inputField")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_error(self, message: str | None) -> None:
        """Toggle the ``error`` dynamic property used by the QSS rule."""
        self.setProperty("error", "true" if message else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class CheckBox(QCheckBox):
    """Design-system checkbox."""

    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setObjectName("designCheckbox")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class IntSpinBox(QSpinBox):
    """Integer spin box using the input-field styling.

    A ``SpinBox`` does not pick up ``QLineEdit#inputField`` styling directly
    (its inner line edit is a child), so this subclass applies the same
    objectName to the inner line edit and sets a calm border via the QSS
    ``QSpinBox`` selector below.
    """

    def __init__(self, minimum: int = 0, maximum: int = 1_000_000_000):
        super().__init__()
        self.setObjectName("inputField")
        self.setMinimum(minimum)
        self.setMaximum(maximum)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Give the numeric input enough room to show several digits comfortably
        # instead of being squeezed to just the spinner arrows in side-by-side
        # form rows (e.g. Quantity + Min stock in the Product dialog).
        self.setMinimumWidth(120)
        inner = self.lineEdit()
        if inner is not None:
            inner.setObjectName("inputField")

    def set_error(self, message: str | None) -> None:
        self.setProperty("error", "true" if message else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class FieldLabel(QLabel):
    """Small label used to caption a form field."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("fieldLabel")


class ErrorLabel(QLabel):
    """Inline validation message label (hidden until a message is set)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("fieldError")
        self.set_word_wrap(True)
        self.set_message(None)

    def set_word_wrap(self, on: bool) -> None:
        self.setWordWrap(on)

    def set_message(self, message: str | None) -> None:
        self.setText(message or "")
        self.setVisible(bool(message))


class Field(QWidget):
    """A labelled form field with an inline error message.

    Compose a form by adding these to a vertical layout::

        name_field = Field("Name", InputField())
        layout.addWidget(name_field)
        # later, on validation:
        name_field.set_error("Name is required.")
    """

    def __init__(self, label: str, control: QWidget):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.label = FieldLabel(label)
        self.control = control
        self.error_label = ErrorLabel()
        layout.addWidget(self.label)
        layout.addWidget(self.control)
        layout.addWidget(self.error_label)

    def set_error(self, message: str | None) -> None:
        self.error_label.set_message(message)
        # Reflect the error state onto the control if it supports it.
        setter = getattr(self.control, "set_error", None)
        if callable(setter):
            setter(message)
