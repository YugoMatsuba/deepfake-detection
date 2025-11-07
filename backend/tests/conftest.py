"""
Pytest configuration for backend tests.

Ensures database engine is initialized before any tests run.
Provides clean database state for each test.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import init_engine, engine as get_engine
from models import Base


@pytest.fixture(scope="session", autouse=True)
def _engine(tmp_path_factory):
    """
    Initialize PostgreSQL test database for entire test session.

    Creates a unique temporary database, runs tests, then cleans up.
    """
    import os
    import uuid

    test_db_url = os.getenv("TEST_DATABASE_URL")

    if not test_db_url or not test_db_url.startswith("postgresql"):
        raise RuntimeError(
            "\n"
            "TEST_DATABASE_URL must be set to a PostgreSQL connection string.\n"
            "\n"
            "For local testing:\n"
            "  1. Start PostgreSQL: docker compose up -d db\n"
            "  2. Set TEST_DATABASE_URL:\n"
            "     export TEST_DATABASE_URL=postgresql+psycopg://deepfake:secret2@localhost:5432\n"
            "  3. Run tests: pytest tests/ -v\n"
            "\n"
            "For Docker container testing:\n"
            "  docker compose exec backend bash -c \\\n"
            '    "TEST_DATABASE_URL=postgresql+psycopg://deepfake:secret2@db:5432 pytest tests/ -v"\n'
            "\n"
            "For CI: GitHub Actions provides PostgreSQL service automatically.\n"
        )

    print(f"Attempting PostgreSQL connection: {test_db_url}")

    # Generate unique database name for this test session
    test_db_name = f"test_{uuid.uuid4().hex[:8]}"
    base_url = test_db_url

    # Extract connection parts to create/drop test database
    from sqlalchemy import create_engine, text

    admin_url = f"{base_url}/postgres"
    test_url = f"{base_url}/{test_db_name}"

    # Create test database
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {test_db_name}"))
    admin_engine.dispose()

    # Initialize test engine
    init_engine(test_url)
    print(f"✓ PostgreSQL test database created: {test_db_name}")

    yield

    # Cleanup: drop test database
    get_engine().dispose()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        # Terminate connections to test database before dropping
        conn.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{test_db_name}'"))
        conn.execute(text(f"DROP DATABASE {test_db_name}"))
    admin_engine.dispose()
    print(f"✓ PostgreSQL test database dropped: {test_db_name}")


@pytest.fixture(autouse=True)
def _schema():
    """
    Provide clean database schema for each test.

    - Drops all tables before test
    - Creates all tables before test
    - Drops all tables after test (cleanup)
    - Ensures test isolation
    """
    eng = get_engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield
    Base.metadata.drop_all(eng)
