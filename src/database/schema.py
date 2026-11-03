"""Versioned schema initialisation facade for Paperite.

This module is the single entry point used at app startup to ensure the
database exists and is migrated to the latest schema. It deliberately stays
thin: the actual schema lives in versioned migrations in
:mod:`src.database.migrations`, and connection handling lives in
:mod:`src.database.connection`.

Typical use::

    from src.database.schema import init_db
    init_db()                 # uses the platform-default user data path
    init_db(path=":memory:")  # tests / tooling

``init_db`` opens a short-lived connection, runs the migration runner, and
closes it. It does not keep a connection open for the app; services (in a
later phase) will open their own connections via
:func:`src.database.connection.open_connection`.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from src.database.connection import open_connection, resolve_db_path
from src.database.migrations import run_migrations


def init_db(path: str | os.PathLike[str] | None = None) -> int:
    """Ensure the database exists and is migrated to the latest version.

    Parameters
    ----------
    path:
        Optional explicit database path. If omitted, the
        ``PAPERITE_DB_PATH`` env var and the platform default apply (see
        :func:`src.database.connection.resolve_db_path`).

    Returns
    -------
    int
        The schema version now applied to the database.

    Raises
    ------
    sqlite3.Error
        If the database cannot be opened or a migration fails. Callers (e.g.
        ``src.main``) are expected to translate this into a user-friendly
        dialog rather than show a raw traceback.
    """
    # In-memory databases (":memory:") need the connection to stay open for the
    # schema to persist, so use a single connection and don't close it until
    # after the migrations. For file databases, open/close is fine.
    conn = open_connection(path)
    try:
        return run_migrations(conn)
    finally:
        conn.close()


__all__ = ["init_db", "resolve_db_path", "run_migrations"]
