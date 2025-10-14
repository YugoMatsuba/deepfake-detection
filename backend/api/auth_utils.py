"""
Authentication and authorization utilities for protected routes.

Provides decorators and helpers for:
- Session-based authentication
- Analysis ownership verification
"""

from __future__ import annotations
from functools import wraps
from typing import Optional

from flask import session, jsonify, abort
from sqlalchemy.orm import Session

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from models import Analysis


def require_login(f):
    """
    Decorator: Ensure user is logged in via session.

    Checks for session["user_id"]. Returns 401 if not authenticated.

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
            return jsonify(error="Unauthorized"), 401
        return f(*args, **kwargs)
    return decorated


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
    """
    # Require login (caller should use @require_login decorator)
    user_id = session.get("user_id")
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
