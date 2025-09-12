"""
Auth routes for A1, A2, A3.

Implements the following endpoints (REST + JSON):

POST /api/auth/register
    Purpose: seed first admin, or admin creates users.
    Body: { "username": "str", "password": "str", "role": "investigator"|"admin"? (optional) }
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

GET /api/auth/audit?limit=100&user_id=...
    Admin-only.
    Returns:
      200 { "logs": [ { "id": int, "user_id": int|null, "event": "login"|"logout"|"login_failed", "ip": "str", "user_agent": "str", "created_at": "ISO8601" }, ... ] }
      403 { "error": "forbidden" }

POST /api/auth/users/<int:user_id>/toggle
    Admin-only; activate/deactivate a user.
    Body: { "active": true|false }
    Returns:
      200 { "id": int, "active": bool }
      404 { "error": "not_found" }
      403 { "error": "forbidden" }
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from flask import Blueprint, request, jsonify, session
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, Session

from api import Base, get_db, hash_password, verify_password  # type: ignore

bp = Blueprint("auth", __name__)

# --- Minimal models colocated for now (move to models/ later) ---

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="investigator")  # "investigator" | "admin"
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    event: Mapped[str] = mapped_column(String(32))  # "login" | "logout" | "login_failed"
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# --- Helpers (no business logic; just parsing/skeletons) ---

def _client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # First IP in the list is the original client
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri
    return request.remote_addr or "0.0.0.0"

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
    TODO: fetch by session.get("user_id")
    """
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)

def _require_admin(db: Session) -> Optional[User]:
    """
    Return current user if admin else None.
    """
    u = _require_auth(db)
    if not u or u.role != "admin" or not u.active:
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
        # TODO: normalize username with .lower() for consistent lookups
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify(error="invalid_payload"), 400

        # any existing users?
        # TODO: use SQLAlchemy 2.x style: db.execute(select(func.count()).select_from(User)).scalar_one()
        count = db.query(User).count()  # SQLAlchemy 2.x allows this legacy; fine for SQLite
        if count > 0:
            admin = _require_admin(db)
            if not admin:
                return jsonify(error="forbidden"), 403

        # unique username
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return jsonify(error="username_taken"), 400

        pw_hash = hash_password(password)
        role = "admin" if count == 0 else "investigator"
        u = User(username=username, password_hash=pw_hash, role=role, active=True)
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
        # TODO: normalize username with .lower() for consistent lookups
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify(error="invalid_credentials"), 401

        u = db.query(User).filter(User.username == username).first()
        if not u:
            db.add(AuditLog(user_id=None, event="login_failed", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="invalid_credentials"), 401

        if not u.active:
            db.add(AuditLog(user_id=u.id, event="login_failed", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="invalid_credentials"), 401

        if not verify_password(u.password_hash, password):
            db.add(AuditLog(user_id=u.id, event="login_failed", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="invalid_credentials"), 401

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

        # create user 
        u = User(
            username=username,
            password_hash=hash_password(password),
            active=True,                 # or rely on model default
            # role defaults to "investigator"
        )
        db.add(u)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            db.add(AuditLog(user_id=None, event="signup_failed_duplicate", ip=_client_ip(), user_agent=_ua()))
            db.commit()
            return jsonify(error="username_taken"), 409

        # success: audit + auto-login
        db.add(AuditLog(user_id=u.id, event="signup", ip=_client_ip(), user_agent=_ua()))
        db.commit()

        session.clear()
        session["user_id"] = u.id
        session["role"] = u.role

        return jsonify(user={"id": u.id, "username": u.username, "role": u.role}), 201

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
    Return current user info.
    Implementation outline:
      - u = _require_auth(db); if None: return 401
      - return {id, username, role}
    """
    with get_db() as db:
        u = _require_auth(db)
        if not u:
            return jsonify(error="unauthenticated"), 401
        return jsonify(user={"id": u.id, "username": u.username, "role": u.role}), 200


@bp.get("/audit")
def audit():
    """
    Admin-only audit log listing.
    Query: limit (int, default 100), user_id (optional)
    Implementation outline:
      - admin = _require_admin(db); if None: return 403
      - fetch last N AuditLog rows; serialize
      - return {logs:[...]}
    """
    with get_db() as db:
        # TODO: implement
        return jsonify(error="forbidden"), 403


@bp.post("/users/<int:user_id>/toggle")
def toggle_user(user_id: int):
    """
    Admin-only: activate/deactivate user.
    Body: { "active": true|false }
    Implementation outline:
      - admin = _require_admin(db); if None: return 403
      - fetch user; if not found: 404
      - set active per body; commit; return {id, active}
    """
    with get_db() as db:
        data = _require_json()
        # TODO: implement
        return jsonify(error="not_implemented"), 501
