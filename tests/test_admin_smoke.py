"""
Smoke tests for admin dashboard approval workflow.

Just 5 critical tests to ensure the core functionality works:
1. Signup creates pending user
2. Login blocks pending user
3. Admin approves, then login works
4. Admin routes require admin role
5. Audit log created on approval
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from api import hash_password, get_db
from models import User, AuditLog


def test_signup_creates_pending_user(client):
    """Test that signup creates a pending user (active=False, pending_approval=True)."""
    resp = client.post("/api/auth/signup", json={
        "username": "newuser",
        "password": "password123"
    })

    assert resp.status_code == 201
    data = resp.json
    assert "Awaiting admin approval" in data["message"]

    # Verify user in database
    with get_db() as db:
        user = db.query(User).filter(User.username == "newuser").first()
        assert user is not None
        assert user.active is False
        assert user.pending_approval is True
        assert user.role == "user"


def test_login_blocks_pending_user(client):
    """Test that login blocks pending approval users with 403."""
    # Create pending user
    with get_db() as db:
        user = User(
            username="pending",
            password_hash=hash_password("password123"),
            role="user",
            active=False,
            pending_approval=True
        )
        db.add(user)
        db.commit()

    # Try to login
    resp = client.post("/api/auth/login", json={
        "username": "pending",
        "password": "password123"
    })

    assert resp.status_code == 403
    data = resp.json
    assert data["error"] == "account_pending_approval"


def test_admin_approves_then_login_works(client):
    """Test full approval workflow: signup → approve → login."""
    # Create admin user
    with get_db() as db:
        admin = User(
            username="admin",
            password_hash=hash_password("adminpass"),
            role="admin",
            active=True,
            pending_approval=False
        )
        pending_user = User(
            username="waitinguser",
            password_hash=hash_password("userpass"),
            role="user",
            active=False,
            pending_approval=True
        )
        db.add(admin)
        db.add(pending_user)
        db.commit()
        pending_user_id = pending_user.id

    # Login blocked before approval
    resp = client.post("/api/auth/login", json={
        "username": "waitinguser",
        "password": "userpass"
    })
    assert resp.status_code == 403

    # Admin logs in
    resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "adminpass"
    })
    assert resp.status_code == 200

    # Admin approves user
    resp = client.post(f"/api/admin/users/{pending_user_id}/approve")
    assert resp.status_code == 200

    # Logout admin (clear session)
    client.post("/api/auth/logout")

    # Now user can login
    resp = client.post("/api/auth/login", json={
        "username": "waitinguser",
        "password": "userpass"
    })
    assert resp.status_code == 200
    data = resp.json
    assert data["user"]["username"] == "waitinguser"


def test_admin_route_requires_admin_role(client):
    """Test that admin routes block regular users with 403."""
    # Create regular user
    with get_db() as db:
        user = User(
            username="regularuser",
            password_hash=hash_password("password123"),
            role="user",
            active=True,
            pending_approval=False
        )
        db.add(user)
        db.commit()

    # Login as regular user
    resp = client.post("/api/auth/login", json={
        "username": "regularuser",
        "password": "password123"
    })
    assert resp.status_code == 200

    # Try to access admin endpoint
    resp = client.get("/api/admin/pending-users")
    assert resp.status_code == 403


def test_audit_log_created_on_approval(client):
    """Test that approving a user creates an audit log entry."""
    # Create admin and pending user
    with get_db() as db:
        admin = User(
            username="admin2",
            password_hash=hash_password("adminpass"),
            role="admin",
            active=True,
            pending_approval=False
        )
        pending_user = User(
            username="tobeapproved",
            password_hash=hash_password("userpass"),
            role="user",
            active=False,
            pending_approval=True
        )
        db.add(admin)
        db.add(pending_user)
        db.commit()
        pending_user_id = pending_user.id
        admin_id = admin.id

    # Admin logs in
    resp = client.post("/api/auth/login", json={
        "username": "admin2",
        "password": "adminpass"
    })
    assert resp.status_code == 200

    # Approve user
    resp = client.post(f"/api/admin/users/{pending_user_id}/approve")
    assert resp.status_code == 200

    # Check audit log
    with get_db() as db:
        log = db.query(AuditLog).filter(
            AuditLog.event == "user_approved"
        ).first()
        assert log is not None
        assert log.user_id == admin_id  # Admin performed the action
        assert log.details_json is not None
        assert log.details_json["target_user_id"] == pending_user_id
