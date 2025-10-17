"""
Pytest configuration for backend tests.

Ensures database engine is initialized before any tests run.
"""
import pytest
from api import init_engine, Base, engine as get_engine


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """
    Initialize in-memory SQLite database once for all tests.

    Runs automatically before any tests (autouse=True).
    Only runs once per test session (scope="session").

    If the engine is already initialized (e.g., locally), does nothing.
    Otherwise, initializes with an in-memory database and creates tables.
    """
    try:
        # Try to get engine - will raise AssertionError if not initialized
        get_engine()
    except AssertionError:
        # Engine not initialized yet, so initialize it with in-memory DB
        init_engine("sqlite:///:memory:")
        # Create all tables from models
        Base.metadata.create_all(get_engine())
