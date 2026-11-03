"""Smoke test for the Paperite proof-of-concept.

This is a trivial harness check: it imports the application module and verifies
the window factory and entry point are exposed. It does not launch a GUI event
loop and, because ``src.main`` imports PySide6 lazily, it does not load the Qt
shared libraries -- so it runs on any host, including headless CI.
"""

import sys
from pathlib import Path

# Make the repo root importable so `import src.main` resolves to the `src`
# namespace package at the project root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def test_main_module_importable():
    """Importing src.main exposes callable entry points (harness wiring)."""
    import src.main

    assert callable(src.main.create_main_window)
    assert callable(src.main.main)
