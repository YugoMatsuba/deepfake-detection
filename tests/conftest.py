"""
Simple test fixtures using in-memory SQLite.

No complex SAVEPOINT transactions - just clean DB state before each test.
"""

import os
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import models
import api as api_module
from app import create_app

# Project root for ML model weights
PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def engine():
    """
    Single in-memory SQLite DB shared by all tests.
    Uses StaticPool to keep the same connection alive.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return eng


@pytest.fixture(scope="session")
def bind_app_to_test_engine(engine):
    """
    Point the app's DB to our test engine and create tables.
    This runs once per test session.
    """
    # Point API module to use test engine
    api_module._engine = engine
    api_module._SessionLocal = sessionmaker(
        bind=engine,
        expire_on_commit=False,
        future=True
    )

    # Create all tables
    models.Base.metadata.create_all(bind=engine)

    yield

    # Teardown: drop all tables
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def app(bind_app_to_test_engine):
    """
    Create Flask app in testing mode.
    Session-scoped so we don't recreate app for each test.
    """
    # Set test environment variables
    os.environ["FLASK_ENV"] = "testing"
    os.environ["SECRET_KEY"] = "test-secret-key"

    # Skip owner bootstrap for tests (we create users manually in tests)
    os.environ["OWNER_USERNAME"] = ""

    # Create Flask app
    flask_app = create_app()
    flask_app.testing = True

    # Configure for testing
    flask_app.config.update({
        "TESTING": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_HTTPONLY": True,
        "SERVER_NAME": "localhost",
    })

    return flask_app


@pytest.fixture()
def client(app, clean_db):
    """
    Create Flask test client.
    Function-scoped so each test gets a fresh client with clean session.

    Depends on clean_db to ensure database is clean before each test.
    """
    with app.test_client() as c, app.app_context():
        yield c


@pytest.fixture()
def clean_db(engine):
    """
    Clean all tables before each test.
    This ensures test isolation without complex SAVEPOINT logic.

    Note: Not autouse - only used by tests that need database (via client fixture).
    """
    # Delete all rows from all tables
    with engine.begin() as conn:
        for table in reversed(models.Base.metadata.sorted_tables):
            conn.execute(table.delete())

    yield

    # No need for explicit cleanup - next test will clean again


# ============================================================================
# ML Model Weight Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def xception_weights_path():
    """Path to Xception model weights for testing."""
    return str(PROJECT_ROOT / "ml" / "weights" / "xception_best.pth")


@pytest.fixture(scope="session")
def spsl_weights_path():
    """Path to SPSL model weights for testing."""
    return str(PROJECT_ROOT / "ml" / "weights" / "spsl_best.pth")


@pytest.fixture(scope="session")
def ucf_weights_path():
    """Path to UCF model weights for testing."""
    return str(PROJECT_ROOT / "ml" / "weights" / "ucf_best.pth")
