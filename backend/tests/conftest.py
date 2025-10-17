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
    Initialize SQLite engine once for entire test session.

    Uses file-backed SQLite to avoid cross-connection issues.
    """
    dbdir = tmp_path_factory.mktemp("db")
    init_engine(f"sqlite:///{dbdir}/test.db")
    yield
    get_engine().dispose()


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
