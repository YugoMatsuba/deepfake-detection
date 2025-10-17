"""
Test admin routes endpoints.

Tests:
- User approval (pending-users, approve, reject)
- Hard delete guards
- Audit logs with JOIN queries
- Analysis management
- Role management with guards
"""

import pytest
import uuid

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from models import User, Analysis, AuditLog


def login_as(client, username, password="password123"):
    """Helper to login as a user."""
    return client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })


# ============================================================================
# User Approval Tests
# ============================================================================

def test_get_pending_users(client, db_session, admin_user, pending_user):
    """Test GET /admin/pending-users returns pending users."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 200

    data = resp.json
    assert "users" in data
    assert len(data["users"]) >= 1

    usernames = [u["username"] for u in data["users"]]
    assert "test_pending" in usernames


def test_approve_user(client, db_session, admin_user, pending_user):
    """Test POST /admin/users/<id>/approve approves user."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{pending_user.id}/approve")
    assert resp.status_code == 200

    # Verify user approved in DB
    db_session.refresh(pending_user)
    assert pending_user.active is True
    assert pending_user.pending_approval is False


def test_reject_user_hard_deletes(client, db_session, admin_user, pending_user):
    """Test POST /admin/users/<id>/reject hard deletes user."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    user_id = pending_user.id
    username = pending_user.username

    resp = client.post(f"/api/admin/users/{user_id}/reject")
    assert resp.status_code == 200

    # Verify user deleted from DB
    user = db_session.query(User).get(user_id)
    assert user is None

    # Verify username can be reused
    new_user = User(
        username=username,
        password_hash="hash",
        role="user",
        active=False,
        pending_approval=True
    )
    db_session.add(new_user)
    db_session.commit()  # Should not fail


def test_reject_user_with_data_fails(client, db_session, admin_user, pending_user):
    """Test reject fails if user has analyses (409)."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    # Create analysis for pending user
    analysis = Analysis(
        id=str(uuid.uuid4()),
        user_id=pending_user.id,
        status="created",
        video_path="/fake/path",
        video_sha256="fake_sha256"
    )
    db_session.add(analysis)
    db_session.commit()

    resp = client.post(f"/api/admin/users/{pending_user.id}/reject")
    assert resp.status_code == 409
    assert resp.json["error"] == "user_has_data"


# ============================================================================
# Audit Log Tests
# ============================================================================

def test_get_audit_logs(client, db_session, admin_user):
    """Test GET /admin/audit-logs returns logs with usernames."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.get("/api/admin/audit-logs")
    assert resp.status_code == 200

    data = resp.json
    assert "logs" in data
    assert "total" in data

    # Verify username included (JOIN query)
    for log in data["logs"]:
        assert "username" in log
        assert "event" in log


def test_audit_log_records_approval(client, db_session, admin_user, pending_user):
    """Test approval creates audit log entry."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{pending_user.id}/approve")
    assert resp.status_code == 200

    # Check audit log
    log = db_session.query(AuditLog).filter(
        AuditLog.event == "user_approved"
    ).first()

    assert log is not None
    assert log.details_json["target_user_id"] == pending_user.id


# ============================================================================
# Analysis Management Tests
# ============================================================================

def test_get_all_analyses(client, db_session, admin_user, analysis):
    """Test GET /admin/analyses returns all analyses with usernames."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.get("/api/admin/analyses")
    assert resp.status_code == 200

    data = resp.json
    assert "analyses" in data
    assert len(data["analyses"]) >= 1

    # Verify username included (JOIN query)
    for a in data["analyses"]:
        assert "username" in a
        assert "status" in a


def test_reassign_analysis(client, db_session, admin_user, regular_user, analysis):
    """Test POST /admin/analyses/<id>/reassign reassigns analysis."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    # Create another user to reassign to
    new_user = User(
        username="new_owner",
        password_hash="hash",
        role="user",
        active=True,
        pending_approval=False
    )
    db_session.add(new_user)
    db_session.commit()

    original_owner = analysis.user_id

    resp = client.post(f"/api/admin/analyses/{analysis.id}/reassign", json={
        "new_user_id": new_user.id
    })
    assert resp.status_code == 200

    # Verify reassignment in DB
    db_session.refresh(analysis)
    assert analysis.user_id == new_user.id
    assert analysis.user_id != original_owner


def test_reassign_to_invalid_user_fails(client, db_session, admin_user, analysis, pending_user):
    """Test reassign to pending user fails."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/analyses/{analysis.id}/reassign", json={
        "new_user_id": pending_user.id
    })
    assert resp.status_code == 400
    assert resp.json["error"] == "invalid_target_user"


# ============================================================================
# User Search Tests
# ============================================================================

def test_search_users(client, db_session, admin_user, regular_user):
    """Test GET /admin/users/search returns matching users."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.get("/api/admin/users/search?q=test_user")
    assert resp.status_code == 200

    data = resp.json
    assert "users" in data
    assert len(data["users"]) >= 1

    usernames = [u["username"] for u in data["users"]]
    assert "test_user" in usernames


def test_search_case_insensitive(client, db_session, admin_user, regular_user):
    """Test search is case-insensitive."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.get("/api/admin/users/search?q=TEST_USER")
    assert resp.status_code == 200

    data = resp.json
    usernames = [u["username"] for u in data["users"]]
    assert "test_user" in usernames


def test_search_excludes_pending_users(client, db_session, admin_user, pending_user):
    """Test search excludes pending users."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.get("/api/admin/users/search?q=pending")
    assert resp.status_code == 200

    data = resp.json
    usernames = [u["username"] for u in data["users"]]
    assert "test_pending" not in usernames


# ============================================================================
# Role Management Tests (Owner Only)
# ============================================================================

def test_promote_user_to_admin(client, db_session, owner_user, regular_user):
    """Test POST /admin/users/<id>/promote promotes user."""
    resp = login_as(client, "test_owner")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{regular_user.id}/promote")
    assert resp.status_code == 200

    # Verify promotion in DB
    db_session.refresh(regular_user)
    assert regular_user.role == "admin"


def test_demote_admin_to_user(client, db_session, owner_user, admin_user):
    """Test POST /admin/users/<id>/demote demotes admin."""
    # Create second admin first (to avoid last admin guard)
    admin2 = User(
        username="admin2",
        password_hash="hash",
        role="admin",
        active=True,
        pending_approval=False
    )
    db_session.add(admin2)
    db_session.commit()

    resp = login_as(client, "test_owner")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{admin_user.id}/demote")
    assert resp.status_code == 200

    # Verify demotion in DB
    db_session.refresh(admin_user)
    assert admin_user.role == "user"


def test_cannot_demote_last_admin(client, db_session, owner_user, admin_user):
    """Test cannot demote last admin (409)."""
    resp = login_as(client, "test_owner")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{admin_user.id}/demote")
    assert resp.status_code == 409
    assert resp.json["error"] == "cannot_demote_last_admin"


def test_cannot_modify_owner(client, db_session, owner_user):
    """Test cannot promote/demote/deactivate owner."""
    # Create second owner to test
    admin = User(
        username="admin_test",
        password_hash="hash",
        role="admin",
        active=True,
        pending_approval=False
    )
    db_session.add(admin)
    db_session.commit()

    resp = login_as(client, "test_owner")
    assert resp.status_code == 200

    # Try to demote owner
    resp = client.post(f"/api/admin/users/{owner_user.id}/demote")
    assert resp.status_code == 403
    assert resp.json["error"] == "cannot_modify_owner"


def test_admin_cannot_promote(client, db_session, admin_user, regular_user):
    """Test admin cannot promote (owner only)."""
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{regular_user.id}/promote")
    assert resp.status_code == 403
    assert resp.json["error"] == "forbidden"


# ============================================================================
# Authorization Tests
# ============================================================================

def test_regular_user_cannot_access_admin_routes(client, db_session, regular_user):
    """Test regular user blocked from admin routes."""
    resp = login_as(client, "test_user")
    assert resp.status_code == 200

    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 403


def test_unauthenticated_cannot_access_admin_routes(client):
    """Test unauthenticated user blocked from admin routes."""
    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 401
