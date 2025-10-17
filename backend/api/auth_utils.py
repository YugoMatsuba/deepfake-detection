"""
Authentication and authorization utilities for protected routes.

Provides decorators and helpers for:
- Session-based authentication
- Role-based authorization (user, admin, owner)
- Analysis ownership verification
- Audit logging
"""

from __future__ import annotations
from functools import wraps
from typing import Optional

from flask import session, jsonify, abort, g, request
from sqlalchemy.orm import Session

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from models import Analysis, User, AuditLog
from api import get_db


# ============================================================================
# User Fetching & Session Helpers
# ============================================================================

def current_user(db: Session) -> User:
    """
    Get current authenticated user from session.

    Raises 401 if not logged in or user not active.
    Stashes user on g.user to avoid repeated DB queries.

    Returns:
        User object (active users only)

    Raises:
        401: Not logged in or user inactive
    """
    # Check if already fetched this request
    if hasattr(g, 'user') and g.user:
        return g.user

    uid = session.get("user_id")
    if not uid:
        abort(401, description="Unauthorized")

    user = db.query(User).get(uid)
    if not user or not user.active:
        abort(401, description="Unauthorized")

    # Cache on request context
    g.user = user
    return user


def _audit_log(db: Session, event: str, user_id: Optional[int] = None, details: Optional[dict] = None):
    """
    Create audit log entry with IP and user agent.

    Args:
        db: SQLAlchemy session
        event: Event name (e.g. "login", "user_approved", "analysis_reassigned")
        user_id: User ID (defaults to session user_id)
        details: Optional structured data (stored in details_json)
    """
    log = AuditLog(
        user_id=user_id or session.get("user_id"),
        event=event,
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        details_json=details
    )
    db.add(log)


# ============================================================================
# Authorization Decorators
# ============================================================================

def require_login(f):
    """
    Decorator: Ensure user is logged in via session (basic check only).

    DEPRECATED: Use require_user instead for routes that need approval check.

    Checks for session["user_id"]. Returns 401 if not authenticated.
    Does NOT check active or pending_approval status.

    Usage:
        @app.route("/protected")
        @require_login
        def protected_route():
            user_id = session["user_id"]  # Guaranteed to exist
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="unauthorized"), 401
        return f(*args, **kwargs)
    return decorated


def require_user(f):
    """
    Decorator: Require authenticated, active, approved user.

    Blocks pending approval users. Sets g.user for downstream use.
    Use this for normal user routes (upload, analysis, etc.).

    Returns:
        - 401: Not logged in or inactive
        - 403: Pending approval
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        with get_db() as db:
            user = current_user(db)  # Raises 401 if missing/inactive

            if user.pending_approval:
                return jsonify(error="account_pending_approval"), 403

            g.user = user
            return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """
    Decorator: Require user to be authenticated and have admin or owner role.

    Use for admin dashboard endpoints (view all data, approve users, etc.).
    Sets g.user for downstream use.

    Returns:
        - 401: Not logged in or inactive
        - 403: Not admin/owner, or pending approval
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        with get_db() as db:
            user = current_user(db)

            if user.role not in ("admin", "owner"):
                return jsonify(error="forbidden"), 403

            if user.pending_approval:
                return jsonify(error="account_pending_approval"), 403

            g.user = user
            return f(*args, **kwargs)
    return wrapper


def require_owner(f):
    """
    Decorator: Require user to be authenticated and have owner role.

    Use for sensitive operations like role changes, user deactivation.
    Sets g.user for downstream use.

    Returns:
        - 401: Not logged in or inactive
        - 403: Not owner
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        with get_db() as db:
            user = current_user(db)

            if user.role != "owner":
                return jsonify(error="forbidden"), 403

            g.user = user
            return f(*args, **kwargs)
    return wrapper


def check_analysis_ownership(db: Session, analysis_id: str) -> Analysis:
    """
    Load analysis and verify current user owns it.

    Args:
        db: SQLAlchemy session
        analysis_id: Analysis UUID

    Returns:
        Analysis object if found and owned by current user

    Raises:
        404: Analysis not found
        403: Analysis exists but user doesn't own it

    Security:
        - Never exposes video_path or other sensitive server-side paths
        - Enforces row-level authorization

    Note:
        Caller must use @require_user decorator which sets g.user
    """
    # g.user already set by @require_user decorator
    user_id = g.user.id if hasattr(g, 'user') and g.user else None
    if not user_id:
        abort(401, description="Unauthorized")

    # Load analysis
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()

    if not analysis:
        abort(404, description="Analysis not found")

    # Check ownership
    if analysis.user_id != user_id:
        abort(403, description="Forbidden: You do not own this analysis")

    return analysis


def get_current_user_id() -> Optional[int]:
    """
    Get current logged-in user ID from session.

    Returns:
        User ID (int) if logged in, None otherwise
    """
    return session.get("user_id")


# ============================================================================
# Admin Guard Rails
# ============================================================================

def count_active_admins(db: Session) -> int:
    """
    Count active users with admin or owner role.

    Used to prevent deleting/demoting the last admin.
    """
    return db.query(User).filter(
        User.role.in_(["admin", "owner"]),
        User.active == True
    ).count()


def is_last_admin(db: Session, user: User) -> bool:
    """
    Check if user is the last active admin/owner.

    Returns:
        True if user is admin/owner, active, and is the only one left
    """
    if user.role not in ("admin", "owner") or not user.active:
        return False
    return count_active_admins(db) == 1
