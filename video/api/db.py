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


def get_db_pool():
    global _pool, _connector
    if _pool is not None:
        return _pool

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        import psycopg2.pool
        logger.info("Initializing psycopg2 SimpleConnectionPool (size 1-2)...")
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
    password = os.getenv("DB_PASS", "")

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
            password=os.getenv("DB_PASS", ""),
            db=os.getenv("DB_NAME", "weaware"),
            ip_type=IPTypes.PUBLIC,
        )
        try:
            yield conn
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
            password=os.getenv("DB_PASS", ""),
        )
        try:
            yield conn
        finally:
            conn.close()
