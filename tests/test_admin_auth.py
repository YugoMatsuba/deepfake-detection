"""
Test auth decorators and authorization logic.

Tests:
- @require_user - blocks pending/inactive users
- @require_admin - only allows admin/owner
- @require_owner - only allows owner
- check_analysis_ownership - uses g.user
- g.user caching - prevents duplicate queries
- Guard rails - last admin, owner protection
"""

import pytest
from flask import g, session
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from api.auth_utils import (
    current_user,
    require_user,
    require_admin,
    require_owner,
    check_analysis_ownership,
    count_active_admins,
    is_last_admin,
    _audit_log
)
from models import User, AuditLog, Analysis


def login_as(client, username, password="password123"):
    """Helper to login as a user."""
    return client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })


# ============================================================================
# current_user() Tests
# ============================================================================

def test_current_user_with_valid_session(client, db_session, regular_user):
    """Test current_user returns user when logged in."""
    with client.session_transaction() as sess:
        sess["user_id"] = regular_user.id

    with client.application.app_context():
        with client.application.test_request_context():
            session["user_id"] = regular_user.id
            user = current_user(db_session)
            assert user.id == regular_user.id
            assert user.username == "test_user"


def test_current_user_caches_on_g(client, db_session, regular_user):
    """Test current_user caches user on g.user."""
    with client.application.app_context():
        with client.application.test_request_context():
            session["user_id"] = regular_user.id

            # First call fetches from DB
            user1 = current_user(db_session)
            assert hasattr(g, 'user')
            assert g.user.id == regular_user.id

            # Second call uses cached g.user
            user2 = current_user(db_session)
            assert user1.id == user2.id


def test_current_user_no_session_raises_401(client, db_session):
    """Test current_user raises 401 when no session."""
    with client.application.app_context():
        with client.application.test_request_context():
            with pytest.raises(Exception):  # werkzeug.exceptions.Unauthorized
                current_user(db_session)


def test_current_user_inactive_raises_401(client, db_session, inactive_user):
    """Test current_user raises 401 for inactive user."""
    with client.application.app_context():
        with client.application.test_request_context():
            session["user_id"] = inactive_user.id
            with pytest.raises(Exception):  # werkzeug.exceptions.Unauthorized
                current_user(db_session)


# ============================================================================
# @require_user Decorator Tests
# ============================================================================

def test_require_user_allows_approved_user(client, regular_user):
    """Test @require_user allows active, approved user."""
    # Login as regular user
    resp = login_as(client, "test_user")
    assert resp.status_code == 200

    # Access protected endpoint
    resp = client.post("/api/videos")  # Uses @require_user
    # Will fail with 400 (no file) but not 401/403 (auth)
    assert resp.status_code == 400  # Missing file, not auth error


def test_require_user_blocks_pending_user(client, pending_user):
    """Test @require_user blocks pending approval user with 403."""
    # Manually set session (login would fail)
    with client.session_transaction() as sess:
        sess["user_id"] = pending_user.id

    # Try to access protected endpoint
    resp = client.post("/api/videos")
    assert resp.status_code == 403
    assert resp.json["error"] == "account_pending_approval"


def test_require_user_blocks_inactive_user(client, inactive_user):
    """Test @require_user blocks inactive user with 401."""
    with client.session_transaction() as sess:
        sess["user_id"] = inactive_user.id

    resp = client.post("/api/videos")
    assert resp.status_code in [401, 403]  # Either is acceptable


def test_require_user_blocks_no_session(client):
    """Test @require_user blocks requests with no session."""
    resp = client.post("/api/videos")
    assert resp.status_code == 401


# ============================================================================
# @require_admin Decorator Tests
# ============================================================================

def test_require_admin_allows_admin(client, admin_user):
    """Test @require_admin allows admin user."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    # Access admin endpoint
    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 200


def test_require_admin_allows_owner(client, owner_user):
    """Test @require_admin allows owner user."""
    resp = login_as(client, "test_owner")
    assert resp.status_code == 200

    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 200


def test_require_admin_blocks_regular_user(client, regular_user):
    """Test @require_admin blocks regular user with 403."""
    resp = login_as(client, "test_user")
    assert resp.status_code == 200

    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 403
    assert resp.json["error"] == "forbidden"


def test_require_admin_blocks_pending_admin(client, db_session):
    """Test @require_admin blocks pending admin with 403."""
    # Create pending admin
    admin = User(
        username="pending_admin",
        password_hash="hash",
        role="admin",
        active=False,
        pending_approval=True
    )
    db_session.add(admin)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = admin.id

    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 403


# ============================================================================
# @require_owner Decorator Tests
# ============================================================================

def test_require_owner_allows_owner(client, owner_user):
    """Test @require_owner allows owner user."""
    resp = login_as(client, "test_owner")
    assert resp.status_code == 200

    # Access owner-only endpoint
    resp = client.post(f"/api/admin/users/{owner_user.id}/promote")
    # Will fail with 400/404 but not 403 (forbidden)
    assert resp.status_code != 403


def test_require_owner_blocks_admin(client, admin_user):
    """Test @require_owner blocks admin user with 403."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{admin_user.id}/promote")
    assert resp.status_code == 403
    assert resp.json["error"] == "forbidden"


def test_require_owner_blocks_regular_user(client, regular_user):
    """Test @require_owner blocks regular user with 403."""
    resp = login_as(client, "test_user")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{regular_user.id}/promote")
    assert resp.status_code == 403


# ============================================================================
# check_analysis_ownership Tests
# ============================================================================

def test_check_analysis_ownership_allows_owner(client, db_session, regular_user, analysis):
    """Test check_analysis_ownership allows owner."""
    resp = login_as(client, "test_user")
    assert resp.status_code == 200

    with client.application.app_context():
        with client.application.test_request_context():
            session["user_id"] = regular_user.id
            g.user = regular_user

            result = check_analysis_ownership(db_session, analysis.id)
            assert result.id == analysis.id


def test_check_analysis_ownership_blocks_other_user(client, db_session, admin_user, analysis):
    """Test check_analysis_ownership blocks non-owner with 403."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    with client.application.app_context():
        with client.application.test_request_context():
            session["user_id"] = admin_user.id
            g.user = admin_user

            with pytest.raises(Exception):  # werkzeug.exceptions.Forbidden
                check_analysis_ownership(db_session, analysis.id)


def test_check_analysis_ownership_404_missing_analysis(client, db_session, regular_user):
    """Test check_analysis_ownership raises 404 for missing analysis."""
    resp = login_as(client, "test_user")
    assert resp.status_code == 200

    with client.application.app_context():
        with client.application.test_request_context():
            session["user_id"] = regular_user.id
            g.user = regular_user

            with pytest.raises(Exception):  # werkzeug.exceptions.NotFound
                check_analysis_ownership(db_session, "fake-analysis-id")


# ============================================================================
# Guard Rails Tests
# ============================================================================

def test_count_active_admins(db_session, owner_user, admin_user, regular_user):
    """Test count_active_admins counts admins and owners."""
    count = count_active_admins(db_session)
    assert count == 2  # owner + admin


def test_count_active_admins_excludes_inactive(db_session, owner_user, admin_user):
    """Test count_active_admins excludes inactive admins."""
    # Deactivate admin
    admin_user.active = False
    db_session.commit()

    count = count_active_admins(db_session)
    assert count == 1  # Only owner


def test_is_last_admin_true_for_only_admin(db_session, admin_user):
    """Test is_last_admin returns True for last admin."""
    result = is_last_admin(db_session, admin_user)
    assert result is True


def test_is_last_admin_false_with_multiple_admins(db_session, owner_user, admin_user):
    """Test is_last_admin returns False when multiple admins exist."""
    result = is_last_admin(db_session, admin_user)
    assert result is False

    result = is_last_admin(db_session, owner_user)
    assert result is False


def test_is_last_admin_false_for_regular_user(db_session, regular_user):
    """Test is_last_admin returns False for non-admin."""
    result = is_last_admin(db_session, regular_user)
    assert result is False


# ============================================================================
# Audit Logging Tests
# ============================================================================

def test_audit_log_creates_entry(client, db_session, regular_user):
    """Test _audit_log creates audit log entry."""
    with client.application.app_context():
        with client.application.test_request_context():
            session["user_id"] = regular_user.id

            _audit_log(db_session, "test_event", details={"key": "value"})
            db_session.commit()

            logs = db_session.query(AuditLog).filter(AuditLog.event == "test_event").all()
            assert len(logs) == 1
            assert logs[0].user_id == regular_user.id
            assert logs[0].details_json == {"key": "value"}


def test_audit_log_captures_ip_and_user_agent(client, db_session, regular_user):
    """Test _audit_log captures IP and user agent."""
    with client.application.app_context():
        with client.application.test_request_context(
            environ_base={"REMOTE_ADDR": "1.2.3.4", "HTTP_USER_AGENT": "TestAgent"}
        ):
            session["user_id"] = regular_user.id

            _audit_log(db_session, "test_event")
            db_session.commit()

            log = db_session.query(AuditLog).filter(AuditLog.event == "test_event").first()
            assert log.ip == "1.2.3.4"
            assert log.user_agent == "TestAgent"
