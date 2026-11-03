"""Database connection management for Paperite.

Responsibilities:

* Resolve the SQLite database file path to a per-user application-data folder
  (``%APPDATA%/Paperite/paperite.db`` on Windows), creating the folder if it
  does not exist.
* Open a :mod:`sqlite3` connection configured for Paperite:

  - ``PRAGMA foreign_keys = ON`` so ``FOREIGN KEY`` constraints are enforced.
  - ``row_factory = sqlite3.Row`` so rows can be accessed by column name.
  - ``detect_types`` including ``sqlite3.PARSE_DECLTYPES`` (room for future
    typed columns).

* Provide an escape hatch for tests and tooling to point at a throwaway
  database via the ``PAPERITE_DB_PATH`` environment variable or an explicit
  ``path`` argument -- without touching the user's real data.

The connection helpers do NOT create the schema; schema initialisation is the
job of :mod:`src.database.schema` / :mod:`src.database.migrations`.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
DEFAULT_DB_FILENAME = "paperite.db"
DB_PATH_ENV_VAR = "PAPERITE_DB_PATH"

_APP_FOLDER = "Paperite"


def default_db_path() -> Path:
    """Return the platform-default path for the user's Paperite database.

    Windows: ``%APPDATA%/Paperite/paperite.db`` (i.e. ``~/AppData/Roaming/...``).
    macOS:   ``~/Library/Application Support/Paperite/paperite.db``.
    Linux:   ``~/.local/share/Paperite/paperite.db`` (XDG_DATA_HOME honoured).

    The parent directory is created if it does not exist. This function never
    raises for a normal user home; if it somehow cannot determine a base
    directory it falls back to ``./Paperite/paperite.db`` relative to the
    current working directory.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )

    if not base:
        base = os.getcwd()

    folder = Path(base) / _APP_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder / DEFAULT_DB_FILENAME


def resolve_db_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the database path, honouring the test/tooling override.

    Resolution order (first wins):

    1. the explicit ``path`` argument, if given;
    2. the ``PAPERITE_DB_PATH`` environment variable, if set; then
    3. :func:`default_db_path`.

    The parent directory of the resulting path is created if missing, so a
    caller can pass a brand-new temp path for tests without extra setup.
    """
    if path is not None:
        p = Path(path)
    elif os.environ.get(DB_PATH_ENV_VAR):
        p = Path(os.environ[DB_PATH_ENV_VAR])
    else:
        return default_db_path()

    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def open_connection(path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    """Open a configured SQLite connection to the Paperite database.

    Parameters
    ----------
    path:
        Optional explicit database path. If omitted, :func:`resolve_db_path`
        is used (so the ``PAPERITE_DB_PATH`` env var and the platform default
        apply).

    Returns
    -------
    sqlite3.Connection
        A connection with foreign keys enabled and ``sqlite3.Row`` rows.

    The caller is responsible for closing the connection (use a ``with``
    statement or a ``try/finally``); :func:`init_db` in :mod:`schema` is the
    only place that opens a connection at app startup.
    """
    db_path = resolve_db_path(path)
    conn = sqlite3.connect(
        str(db_path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        # Default isolation level (deferred): sqlite3 opens an implicit
        # transaction before DML and the caller commits/rolls back. This keeps
        # the migration runner's conn.commit()/conn.rollback() semantics clean;
        # executescript() (which auto-commits) is avoided in migrations.
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
