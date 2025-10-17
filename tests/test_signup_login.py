"""
Test signup and login approval workflow.

Tests:
- Signup creates pending users (active=False, pending_approval=True)
- Signup does NOT auto-login
- Login blocks pending users (403)
- Login blocks inactive users (403)
- /me returns full user object
"""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from models import User, AuditLog


def login_as(client, username, password="password123"):
    """Helper to login as a user."""
    return client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })


# ============================================================================
# Signup Tests
# ============================================================================

def test_signup_creates_pending_user(client, db_session):
    """Test signup creates user with pending_approval=True."""
    resp = client.post("/api/auth/signup", json={
        "username": "newuser",
        "password": "password123"
    })

    assert resp.status_code == 201
    data = resp.json
    assert "message" in data
    assert "awaiting admin approval" in data["message"].lower()
    assert "user_id" in data

    # Verify user in DB
    user = db_session.query(User).filter(User.username == "newuser").first()
    assert user is not None
    assert user.active is False
    assert user.pending_approval is True
    assert user.role == "user"


def test_signup_does_not_auto_login(client, db_session):
    """Test signup does NOT auto-login user."""
    resp = client.post("/api/auth/signup", json={
        "username": "newuser2",
        "password": "password123"
    })

    assert resp.status_code == 201

    # Try to access protected endpoint
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401  # Not logged in


def test_signup_duplicate_username(client, db_session, regular_user):
    """Test signup fails with duplicate username."""
    resp = client.post("/api/auth/signup", json={
        "username": "test_user",  # Already exists
        "password": "password123"
    })

    assert resp.status_code == 409
    assert resp.json["error"] == "username_taken"


def test_signup_logs_pending_event(client, db_session):
    """Test signup logs signup_pending event."""
    resp = client.post("/api/auth/signup", json={
        "username": "newuser3",
        "password": "password123"
    })

    assert resp.status_code == 201

    # Check audit log
    user = db_session.query(User).filter(User.username == "newuser3").first()
    log = db_session.query(AuditLog).filter(
        AuditLog.user_id == user.id,
        AuditLog.event == "signup_pending"
    ).first()

    assert log is not None


# ============================================================================
# Login Tests
# ============================================================================

def test_login_blocks_pending_user(client, db_session, pending_user):
    """Test login blocks pending approval user with 403."""
    resp = client.post("/api/auth/login", json={
        "username": "test_pending",
        "password": "password123"
    })

    assert resp.status_code == 403
    assert resp.json["error"] == "account_pending_approval"


def test_login_blocks_inactive_user(client, db_session, inactive_user):
    """Test login blocks inactive user with 403."""
    resp = client.post("/api/auth/login", json={
        "username": "test_inactive",
        "password": "password123"
    })

    assert resp.status_code == 403
    assert resp.json["error"] == "account_pending_approval"


def test_login_allows_approved_user(client, db_session, regular_user):
    """Test login allows active, approved user."""
    resp = login_as(client, "test_user")

    assert resp.status_code == 200
    data = resp.json
    assert "user" in data
    assert data["user"]["username"] == "test_user"
    assert data["user"]["role"] == "user"


def test_login_logs_failed_pending_event(client, db_session, pending_user):
    """Test login logs login_failed_pending for pending user."""
    resp = client.post("/api/auth/login", json={
        "username": "test_pending",
        "password": "password123"
    })

    assert resp.status_code == 403

    # Check audit log
    log = db_session.query(AuditLog).filter(
        AuditLog.user_id == pending_user.id,
        AuditLog.event == "login_failed_pending"
    ).first()

    assert log is not None


# ============================================================================
# /me Endpoint Tests
# ============================================================================

def test_me_returns_full_user_object(client, db_session, regular_user):
    """Test /me returns user with pending_approval and active fields."""
    resp = login_as(client, "test_user")
    assert resp.status_code == 200

    resp = client.get("/api/auth/me")
    assert resp.status_code == 200

    data = resp.json
    assert "user" in data
    user = data["user"]

    assert "id" in user
    assert "username" in user
    assert "role" in user
    assert "active" in user
    assert "pending_approval" in user

    assert user["username"] == "test_user"
    assert user["active"] is True
    assert user["pending_approval"] is False


def test_me_unauthenticated_returns_401(client):
    """Test /me returns 401 when not logged in."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_approval_workflow(client, db_session, admin_user):
    """Test complete workflow: signup → pending → approve → login."""
    # 1. Signup new user
    resp = client.post("/api/auth/signup", json={
        "username": "workflow_user",
        "password": "password123"
    })
    assert resp.status_code == 201
    user_id = resp.json["user_id"]

    # 2. Cannot login (pending)
    resp = client.post("/api/auth/login", json={
        "username": "workflow_user",
        "password": "password123"
    })
    assert resp.status_code == 403

    # 3. Admin approves user
    resp = login_as(client, "test_admin")
    assert resp.status_code == 200

    resp = client.post(f"/api/admin/users/{user_id}/approve")
    assert resp.status_code == 200

    # 4. User can now login
    client.get("/api/auth/logout")  # Logout admin

    resp = client.post("/api/auth/login", json={
        "username": "workflow_user",
        "password": "password123"
    })
    assert resp.status_code == 200

    # 5. Verify user is approved in DB
    user = db_session.query(User).get(user_id)
    assert user.active is True
    assert user.pending_approval is False
