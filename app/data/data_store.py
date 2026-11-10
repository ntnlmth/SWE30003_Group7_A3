"""DataStore: the single access point for persistent data.

Implements the «Singleton» DataStore from the Assignment 2 design
(CRC card 5.26) on top of SQLite. Every other class saves and finds
objects through it instead of opening the database itself.
"""

import os
import sqlite3
from contextlib import closing

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")


class DataStore:
    """Save and find stored objects in the SQLite database."""

    _instance = None

    def __init__(self, path):
        """Create a DataStore for the database file at ``path``.

        Use :meth:`get_instance` instead of calling this directly.
        """
        self._path = path

    @classmethod
    def get_instance(cls, path=None):
        """Return the single DataStore, creating it on first use.

        Args:
            path: Database file to use. Passing a different path points
                the existing instance at that file, which the tests use
                to work on a temporary database.
        """
        if cls._instance is None:
            if path is None:
                raise RuntimeError("DataStore needs a database path first.")
            cls._instance = cls(path)
        elif path is not None and path != cls._instance._path:
            cls._instance._path = path
        return cls._instance

    def _connect(self):
        """Open a connection that returns rows as dictionaries."""
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_schema(self):
        """Create any tables that do not exist yet."""
        with open(SCHEMA_FILE, encoding="utf-8") as schema:
            script = schema.read()
        with closing(self._connect()) as connection:
            connection.executescript(script)
            connection.commit()

    def execute(self, sql, params=()):
        """Run an insert, update or delete and commit it.

        Returns:
            The id of the last inserted row, if any.
        """
        with closing(self._connect()) as connection:
            cursor = connection.execute(sql, params)
            connection.commit()
            return cursor.lastrowid

    def find_one(self, sql, params=()):
        """Return the first matching row as a dict, or None."""
        with closing(self._connect()) as connection:
            row = connection.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def find_all(self, sql, params=()):
        """Return every matching row as a list of dicts."""
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
