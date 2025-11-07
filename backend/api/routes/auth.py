"""
Auth routes for A1, A2, A3.

Implements the following endpoints (REST + JSON):

POST /api/auth/register
    Purpose: seed first admin, or admin creates users.
    Body: { "username": "str", "password": "str", "role": "user"|"admin"? (optional) }
    Returns:
      201 { "id": int, "username": "str", "role": "str", "active": true }
      400 { "error": "username_taken" | "invalid_payload" }
      403 { "error": "forbidden" } (if not first user and caller is not admin)

POST /api/auth/login
    Body: { "username": "str", "password": "str" }
    Sets: HttpOnly session cookie on success.
    Returns:
      200 { "user": { "id": int, "username": "str", "role": "str" } }
      401 { "error": "invalid_credentials" }
      403 { "error": "inactive_user" }

POST /api/auth/logout
    Clears session.
    Returns:
      204 (no body)

GET /api/auth/me
    Returns:
      200 { "id": int, "username": "str", "role": "str" }
      401 { "error": "unauthenticated" }
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy.exc import IntegrityError
from flask import Blueprint, request, jsonify, session
from sqlalchemy.orm import Session

from api import get_db, hash_password, verify_password  # type: ignore

# Import models from consolidated models.py (now managed by Alembic)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from models import User, AuditLog

bp = Blueprint("auth", __name__)


# --- Helpers (no business logic; just parsing/skeletons) ---


def _client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # First IP in the list is the original client
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri
    return request.remote_addr or "unknown"


def _ua() -> str:
    return request.headers.get("User-Agent", "")


def _require_json() -> dict:
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _require_auth(db: Session) -> Optional[User]:
    """
    Return current user or None.
    """
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def _require_admin(db: Session) -> Optional[User]:
    """
    Return current user if admin or owner else None.
    """
    u = _require_auth(db)
    if not u or u.role not in ("admin", "owner") or not u.active:
        return None
    return u


# --- Endpoints (skeletons only) ---


@bp.post("/register")
def register():
    """
    Seed first admin user, or admin creates users.
    Implementation outline:
      - parse body; validate username/password
      - if no users in DB: create user with role="admin"
      - else: require _require_admin(db)
      - hash_password(); insert row; commit
      - return 201 with new user summary
    """
    with get_db() as db:
        data = _require_json()
        username = (data.get("username") or "").strip().lower()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify(error="invalid_payload"), 400

        # any existing users?
        count = db.query(User).count()
        if count > 0:
            admin = _require_admin(db)
            if not admin:
                return jsonify(error="forbidden"), 403

        # unique username
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return jsonify(error="username_taken"), 400

        pw_hash = hash_password(password)
        role = "admin" if count == 0 else "user"
        u = User(username=username, password_hash=pw_hash, role=role, active=True, pending_approval=False)
        db.add(u)
        db.commit()
        db.refresh(u)
        return jsonify(id=u.id, username=u.username, role=u.role, active=u.active), 201


@bp.post("/login")
def login():
    """
    Log a user in.
    Implementation outline:
      - parse body; look up user; check active; verify_password()
      - on success: session["user_id"] = user.id; session["role"] = user.role
      - insert AuditLog(event="login", ip=_client_ip(), user_agent=_ua())
      - return 200 with user summary
      - on failure: insert AuditLog(event="login_failed", ...); return 401/403
    """
    with get_db() as db:
        data = _require_json()
        username = (data.get("username") or "").strip().lower()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify(error="invalid_credentials"), 401

        u = db.query(User).filter(User.username == username).first()
        if not u:
            db.add(AuditLog(user_id=None, event="login_failed", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="invalid_credentials"), 401

        if not verify_password(u.password_hash, password):
            db.add(AuditLog(user_id=u.id, event="login_failed", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="invalid_credentials"), 401

        # Block inactive or pending approval users
        if not u.active or u.pending_approval:
            db.add(AuditLog(user_id=u.id, event="login_failed_pending", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="account_pending_approval"), 403

        # success
        session.clear()  # prevent fixation
        session["user_id"] = u.id
        session["role"] = u.role
        db.add(AuditLog(user_id=u.id, event="login", ip=_client_ip(), user_agent=_ua()))
        db.commit()
        return jsonify(user={"id": u.id, "username": u.username, "role": u.role}), 200


@bp.post("/signup")
def signup():
    """
    Create a new user account (no email).
    - 400 invalid_request / weak_password
    - 409 username_taken
    - 201 { user: ... } and sets session
    """
    with get_db() as db:
        data = _require_json()
        username = (data.get("username") or "").strip().lower()
        password = data.get("password") or ""

        # basic validation
        if not username or not password:
            db.add(AuditLog(user_id=None, event="signup_failed_invalid", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="invalid_request"), 400

        # pre-check for duplicate (race-safe via IntegrityError below)
        exists = db.query(User.id).filter(User.username == username).first()
        if exists:
            db.add(AuditLog(user_id=None, event="signup_failed_duplicate", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="username_taken"), 409

        # create user in pending state (requires admin approval)
        u = User(
            username=username,
            password_hash=hash_password(password),
            role="user",  # default role
            active=False,  # pending approval
            pending_approval=True,  # requires admin approval
        )
        db.add(u)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            db.add(AuditLog(user_id=None, event="signup_failed_duplicate", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="username_taken"), 409

        # success: audit, NO auto-login (pending approval)
        db.add(AuditLog(user_id=u.id, event="signup_pending", ip=_client_ip(), user_agent=_ua()))
        db.commit()

        # Do NOT auto-login; user needs approval first
        return jsonify(message="Account created. Awaiting admin approval.", user_id=u.id), 201


@bp.post("/logout")
def logout():
    """
    Log a user out.
    Implementation outline:
      - if session has user_id: insert AuditLog(event="logout", ...)
      - clear session
      - return 204
    """
    with get_db() as db:
        uid = session.get("user_id")
        session.clear()
        if uid:
            db.add(AuditLog(user_id=uid, event="logout", ip=_client_ip(), user_agent=_ua()))
            db.commit()
        return ("", 204)


@bp.get("/me")
def me():
    """
    Return current user info including approval status.
    Uses current_user() from auth_utils for consistency and g.user caching.
    """
    from api.auth_utils import current_user

    with get_db() as db:
        try:
            user = current_user(db)  # Raises 401 if not logged in or inactive
            return (
                jsonify(
                    user={
                        "id": user.id,
                        "username": user.username,
                        "role": user.role,
                        "active": user.active,
                        "pending_approval": user.pending_approval,
                    }
                ),
                200,
            )
        except Exception:
            return jsonify(error="unauthenticated"), 401
