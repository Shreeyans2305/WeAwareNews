"""
Database connection and pool manager for WeAware Video API.
Scoped connection pool (1-2 connections) to protect Cloud SQL db-f1-micro.
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator

logger = logging.getLogger(__name__)

_pool = None
_connector = None


def _get_db_password() -> str:
    return os.getenv("DB_PASS") or os.getenv("DB_PASSWORD") or ""


class RowDict(dict):
    """Dictionary representing a database row, accessible by column name or integer index."""
    def __init__(self, col_names, values):
        super().__init__(zip(col_names, values))
        self._values = list(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class DictCursorWrapper:
    """Wrapper around DB-API cursors (like pg8000) to support context manager & dict rows."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        if params is not None:
            return self._cursor.execute(query, params)
        return self._cursor.execute(query)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        col_names = [d[0] for d in self._cursor.description]
        return RowDict(col_names, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return rows
        col_names = [d[0] for d in self._cursor.description]
        return [RowDict(col_names, r) for r in rows]

    @property
    def description(self):
        return getattr(self._cursor, "description", None)

    @property
    def rowcount(self):
        return getattr(self._cursor, "rowcount", -1)

    def close(self):
        if hasattr(self._cursor, "close"):
            self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class Pg8000ConnectionWrapper:
    """Wraps pg8000 connection so .cursor() returns DictCursorWrapper with context manager support."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        cur = self._conn.cursor()
        return DictCursorWrapper(cur)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_dict_cursor(conn):
    """Returns a dict cursor supporting both psycopg2 and pg8000 connections."""
    try:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    except (TypeError, AttributeError):
        return DictCursorWrapper(conn.cursor())


def get_db_pool():
    global _pool, _connector
    if _pool is not None:
        return _pool

    database_url = os.getenv("DATABASE_URL")
    db_pass = _get_db_password()
    if database_url:
        import psycopg2.pool
        logger.info("Initializing psycopg2 SimpleConnectionPool (size 1-2)...")
        if db_pass:
            _pool = psycopg2.pool.SimpleConnectionPool(1, 2, dsn=database_url, password=db_pass)
        else:
            _pool = psycopg2.pool.SimpleConnectionPool(1, 2, dsn=database_url)
        return _pool

    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    if instance_connection_name:
        from google.cloud.sql.connector import Connector, IPTypes
        import pg8000
        logger.info(f"Initializing Cloud SQL Connector for {instance_connection_name}...")
        _connector = Connector()
        return None

    # Fallback to local default Postgres parameters
    import psycopg2.pool
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = os.getenv("DB_NAME", "weaware")
    user = os.getenv("DB_USER", "weaware_user")
    password = _get_db_password()

    try:
        _pool = psycopg2.pool.SimpleConnectionPool(
            1, 2,
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=10,
        )
    except Exception as e:
        logger.warning(f"Could not connect pool to Postgres ({e}). Fallback to dummy or mock if in test.")
        _pool = None

    return _pool


@contextmanager
def get_db_connection() -> Generator:
    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
    if instance_connection_name:
        global _connector
        from google.cloud.sql.connector import Connector, IPTypes
        if _connector is None:
            _connector = Connector()
        conn = _connector.connect(
            instance_connection_name,
            "pg8000",
            user=os.getenv("DB_USER", "weaware_user"),
            password=_get_db_password(),
            db=os.getenv("DB_NAME", "weaware"),
            ip_type=IPTypes.PUBLIC,
        )
        try:
            yield Pg8000ConnectionWrapper(conn)
        finally:
            conn.close()
        return

    pool = get_db_pool()
    if pool is not None:
        conn = pool.getconn()
        try:
            yield conn
        finally:
            pool.putconn(conn)
    else:
        # Direct fallback for tests using injected connection
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME", "weaware"),
            user=os.getenv("DB_USER", "weaware_user"),
            password=_get_db_password(),
        )
        try:
            yield conn
        finally:
            conn.close()
