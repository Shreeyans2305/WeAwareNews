import os
import sys
from pathlib import Path
import psycopg2
import pytest

# Ensure repo root and backend are in sys.path for test execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

for p in [str(REPO_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:testpass@127.0.0.1:5434/weaware_test")


@pytest.fixture(scope="session")
def setup_pg_database():
    """Ensure test tables exist in local PostgreSQL loaded directly from raw prod schema."""
    try:
        conn = psycopg2.connect(TEST_DB_URL, connect_timeout=2)
    except Exception:
        pytest.skip(f"Local PostgreSQL not reachable at {TEST_DB_URL}")
        return

    with conn.cursor() as cur:
        # Load raw production schema from fixtures/prod_schema.sql
        prod_schema_sql = (Path(__file__).parent / "fixtures" / "prod_schema.sql").read_text()
        cur.execute(prod_schema_sql)

        # Migration DDL (with lock_timeout)
        migration_sql = (REPO_ROOT / "video" / "migrations" / "001_create_video_runs.sql").read_text()
        cur.execute(migration_sql)
    conn.commit()
    conn.close()

