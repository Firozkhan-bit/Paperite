"""Paperite application MainWindow shell.

Phase 2: a left sidebar with eight navigation entries and a right
``QStackedWidget`` content area that swaps placeholder pages. No business
logic, database, or services are wired here -- every page is a clearly labelled
placeholder that consumes the design system from :mod:`src.ui.theme`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import PageHeader, SidebarNavItem, SPACE

# Navigation entries (order is significant: index == stacked page index).
NAV_ENTRIES: list[str] = [
    "Dashboard",
    "Products",
    "Categories",
    "Suppliers",
    "Purchases",
    "Sales",
    "Reports",
    "Settings",
]


class _PlaceholderPage(QWidget):
    """Empty placeholder page: a page header and a 'Coming soon' notice.

    Clearly labelled as a placeholder so it is never mistaken for a finished
    feature.
    """

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE[4], SPACE[4], SPACE[4], SPACE[4])
        layout.setSpacing(SPACE[3])

        header = PageHeader(title, "Coming soon")
        layout.addWidget(header)

        notice = QLabel("This section is not built yet.")
        notice.setObjectName("comingSoon")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        badge_frame = QFrame()
        badge_frame.setObjectName("placeholderBadge")
        badge_layout = QHBoxLayout(badge_frame)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_text = QLabel("PLACEHOLDER")
        badge_text.setObjectName("badgeText")
        badge_layout.addWidget(badge_text)
        badge_layout.addStretch(1)
        layout.addWidget(badge_frame)

        layout.addStretch(1)


class MainWindow(QMainWindow):
    """Application shell: sidebar nav + stacked content pages."""

    NAV: list[str] = NAV_ENTRIES

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Paperite")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        central = QWidget(self)
        central.setObjectName("MainWindow")
        self.setCentralWidget(central)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # The stack must exist before the sidebar is built: the sidebar's nav
        # group is connected to self.stack.setCurrentIndex.
        self.stack = QStackedWidget()
        self._build_pages()

        self.nav_buttons: list[QPushButton] = []  # type: ignore[name-defined]
        self.sidebar = self._build_sidebar()
        outer.addWidget(self.sidebar)
        outer.addWidget(self.stack, 1)

        # Select the first page (Dashboard) by default.
        self.nav_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)

    def _build_sidebar(self) -> QFrame:
        from PySide6.QtWidgets import QPushButton  # for the type hint above

        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(220)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, SPACE[4], 0, SPACE[4])
        layout.setSpacing(4)

        brand = QLabel("Paperite")
        brand.setObjectName("brand")
        layout.addWidget(brand)

        brand_caption = QLabel("Stationery inventory")
        brand_caption.setObjectName("brandCaption")
        layout.addWidget(brand_caption)

        # Exclusive group so only one nav item is checked at a time.
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)

        for index, name in enumerate(self.NAV):
            item = SidebarNavItem(name)
            self.nav_group.addButton(item, index)
            self.nav_buttons.append(item)
            layout.addWidget(item)

        layout.addStretch(1)
        return frame

    def _build_pages(self) -> None:
        for index, name in enumerate(self.NAV):
            if name == "Products":
                from src.ui.products.products_page import ProductsPage

                self.stack.addWidget(ProductsPage())
            else:
                self.stack.addWidget(_PlaceholderPage(name))

    def select_page(self, index: int) -> None:
        """Programmatically activate a nav entry by its 0-based index."""
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)
            self.stack.setCurrentIndex(index)
