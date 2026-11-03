"""Paperite -- offline-first desktop inventory app for a small stationery shop.

Phase 3: startup now ensures the SQLite database exists and is migrated before
the window is shown. Database initialisation failures are surfaced as a
user-friendly message box rather than a raw traceback.

PySide6 imports remain lazy (inside functions) so that importing this module is
side-effect free: it does not load the Qt shared libraries, which keeps the
Phase 1 smoke test (``import src.main``) runnable on a headless host.
"""

from __future__ import annotations

import os
import sys

# Ensure the repo root (the parent of this file's `src/` directory) is importable
# so package-absolute imports like `from src.ui.theme import ...` resolve when
# this file is executed directly as `python src/main.py`. This is side-effect
# free: it only touches sys.path and does not load any Qt shared libraries, so
# importing this module (e.g. the Phase 1 smoke test) stays light.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def create_main_window():
    """Create and return the application MainWindow without showing it.

    Keeping window construction separate from the event loop makes the window
    factory importable and testable without launching a GUI.
    """
    from src.ui.main_window import MainWindow

    return MainWindow()


def _initialize_database():
    """Ensure the database exists and is migrated.

    Returns True on success, False on failure (after showing a user-friendly
    dialog). Never raises a raw traceback to the user.
    """
    import logging

    from src.database.schema import init_db

    logger = logging.getLogger("paperite")
    try:
        version = init_db()
        logger.info("Database ready (schema version %s).", version)
        return True
    except Exception as exc:  # noqa: BLE001 -- surfaced to the user below
        logger.exception("Database initialisation failed")
        _show_database_error(str(exc))
        return False


def _show_database_error(message: str) -> None:
    """Display a user-friendly database error dialog (stub).

    This is a minimal stub dialog for Phase 3; it can be replaced with a
    richer component from the design system in a later phase. It deliberately
    avoids importing the heavy Qt widgets at module import time.
    """
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("Paperite - Database error")
    box.setText("Paperite could not start its database.")
    box.setInformativeText(
        "The local database could not be opened or migrated. Please check "
        "that the application data folder is writable and try again."
    )
    box.setDetailedText(message)
    box.exec()


def main() -> int:
    """Application entry point: init DB, build the window, show it, run loop."""
    from PySide6.QtWidgets import QApplication

    from src.ui.theme import apply_theme

    app = QApplication(sys.argv)
    apply_theme(app)

    if not _initialize_database():
        # A database failure is fatal for now: the app cannot function without
        # its local store. The error dialog has already been shown.
        return 1

    window = create_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
