"""Phase 2: MainWindow shell -- navigation switches the stacked page index.

Constructs :class:`~src.ui.main_window.MainWindow` under the Qt "offscreen"
platform (no GUI event loop) and asserts that activating each sidebar nav
entry changes the ``QStackedWidget`` current index.

Because ``src.main`` imports PySide6 lazily, importing this test module does
not load the Qt shared libraries on its own. Constructing ``MainWindow`` does,
however, require ``PySide6.QtWidgets`` to be loadable. On hosts where the Qt
GUI shared libraries cannot load (e.g. a headless sandbox missing the system
``libEGL.so.1``), the test is skipped rather than errored, keeping the suite
green everywhere; on the Windows target (and any host with a real EGL/GL
stack) it runs for real.
"""

import os
import sys
from pathlib import Path

# Make the repo root importable so `import src...` resolves to the `src`
# namespace package at the project root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Force the headless Qt platform BEFORE any QApplication is constructed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def _qt_widgets_available() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _qt_widgets_available(),
    reason="PySide6 QtWidgets unavailable (headless host missing libEGL.so.1)",
)


@pytest.fixture(autouse=True)
def _initialised_tmp_db(tmp_path, monkeypatch):
    """Provide a migrated temp database for each nav test.

    Since Phase 4, the MainWindow builds the real ProductsPage, which queries
    the database at construction. The app always runs init_db at startup before
    showing the window, so these tests do the same with a throwaway DB.
    """
    from src.database.schema import init_db

    db = tmp_path / "paperite_nav_test.db"
    monkeypatch.setenv("PAPERITE_DB_PATH", str(db))
    init_db(str(db))
    yield


def test_nav_entries_match_nav_list():
    """MainWindow exposes one nav button per NAV entry."""
    from PySide6.QtWidgets import QApplication

    from src.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        assert len(win.nav_buttons) == len(MainWindow.NAV)
        for btn, name in zip(win.nav_buttons, MainWindow.NAV):
            assert btn.text() == name
    finally:
        win.close()


def test_nav_clicks_switch_stack_index():
    """Clicking each sidebar nav item switches the stacked page index."""
    from PySide6.QtWidgets import QApplication

    from src.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        for i, btn in enumerate(win.nav_buttons):
            btn.click()
            assert win.stack.currentIndex() == i, (
                f"nav item {i} ({MainWindow.NAV[i]!r}) did not switch stack index "
                f"(got {win.stack.currentIndex()})"
            )
    finally:
        win.close()


def test_select_page_helper_switches_index():
    """The select_page helper activates the expected page."""
    from PySide6.QtWidgets import QApplication

    from src.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        for i in range(len(MainWindow.NAV)):
            win.select_page(i)
            assert win.stack.currentIndex() == i
    finally:
        win.close()
