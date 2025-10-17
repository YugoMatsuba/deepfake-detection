"""
Pytest configuration and fixtures for backend tests.

Provides:
- Flask app with test config
- Test database (in-memory SQLite)
- Test client with session support
- User fixtures (owner, admin, regular, pending)
- Analysis fixtures
"""

import pytest
import os
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Import backend modules
from api import Base, hash_password
from models import User, Analysis, AuditLog
import app as app_module


@pytest.fixture(scope="function")
def test_db():
    """
    Create in-memory test database.

    Yields:
        SQLAlchemy engine with all tables created

    Cleanup:
        Drops all tables after test
    """
    # In-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db):
    """
    Create SQLAlchemy session for test.

    Yields:
        Scoped session connected to test_db

    Cleanup:
        Rolls back and closes session after test
    """
    Session = scoped_session(sessionmaker(bind=test_db))
    session = Session()

    yield session

    session.rollback()
    session.close()
    Session.remove()


@pytest.fixture(scope="function")
def app(test_db, monkeypatch):
    """
    Create Flask test app with test database.

    Args:
        test_db: Test database fixture
        monkeypatch: Pytest monkeypatch for env vars

    Yields:
        Flask app configured for testing
    """
    # Set test environment variables
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Patch db_engine to use test_db
    monkeypatch.setattr(app_module, "db_engine", lambda: test_db)

    # Patch get_db to use test_db
    original_get_db = app_module.get_db

    def test_get_db():
        Session = scoped_session(sessionmaker(bind=test_db))
        try:
            yield Session()
        finally:
            Session.remove()

    monkeypatch.setattr("api.get_db", test_get_db)
    monkeypatch.setattr("backend.api.get_db", test_get_db)

    # Initialize app
    from api import init_engine
    init_engine(db_url="sqlite:///:memory:")

    # Create app without calling bootstrap_owner_from_env
    test_app = Flask(__name__)
    test_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
    })

    # Register blueprints
    from api.routes.auth import bp as auth_bp
    from api.routes.admin import admin_bp
    from api.routes.video_upload import video_bp
    from api.routes.analysis import analysis_bp

    test_app.register_blueprint(auth_bp, url_prefix="/api/auth")
    test_app.register_blueprint(admin_bp, url_prefix="/api/admin")
    test_app.register_blueprint(video_bp, url_prefix="/api")
    test_app.register_blueprint(analysis_bp, url_prefix="/api")

    yield test_app


@pytest.fixture(scope="function")
def client(app):
    """
    Create Flask test client.

    Args:
        app: Flask app fixture

    Yields:
        Test client with session support
    """
    return app.test_client()


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def owner_user(db_session):
    """
    Create owner user.

    Returns:
        User object with role="owner"
    """
    user = User(
        username="test_owner",
        password_hash=hash_password("password123"),
        role="owner",
        active=True,
        pending_approval=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db_session):
    """
    Create admin user.

    Returns:
        User object with role="admin"
    """
    user = User(
        username="test_admin",
        password_hash=hash_password("password123"),
        role="admin",
        active=True,
        pending_approval=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def regular_user(db_session):
    """
    Create regular approved user.

    Returns:
        User object with role="user", approved
    """
    user = User(
        username="test_user",
        password_hash=hash_password("password123"),
        role="user",
        active=True,
        pending_approval=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def pending_user(db_session):
    """
    Create pending approval user.

    Returns:
        User object with pending_approval=True
    """
    user = User(
        username="test_pending",
        password_hash=hash_password("password123"),
        role="user",
        active=False,
        pending_approval=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def inactive_user(db_session):
    """
    Create inactive user.

    Returns:
        User object with active=False
    """
    user = User(
        username="test_inactive",
        password_hash=hash_password("password123"),
        role="user",
        active=False,
        pending_approval=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ============================================================================
# Analysis Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def analysis(db_session, regular_user):
    """
    Create analysis owned by regular_user.

    Returns:
        Analysis object
    """
    import uuid
    analysis = Analysis(
        id=str(uuid.uuid4()),
        user_id=regular_user.id,
        status="created",
        video_path="/fake/path/video.mp4",
        video_sha256="fake_sha256",
        metadata_json={"fps": 30, "frame_count": 100}
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)
    return analysis


# ============================================================================
# Helper Functions
# ============================================================================

def login_as(client, username, password="password123"):
    """
    Helper to login as a user and return response.

    Args:
        client: Flask test client
        username: Username to login
        password: Password (default "password123")

    Returns:
        Response object from login request
    """
    return client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })
