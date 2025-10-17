"""
Admin routes for user approval, audit logs, and analysis management.

All endpoints require @require_admin or @require_owner decorator.
Implements N+1 prevention with JOIN queries.

Endpoints:
- GET /api/admin/pending-users - List users awaiting approval
- POST /api/admin/users/<id>/approve - Approve pending user
- POST /api/admin/users/<id>/reject - Reject and HARD DELETE pending user
- GET /api/admin/audit-logs - View audit logs with username JOIN
- GET /api/admin/analyses - View all analyses with username JOIN
- POST /api/admin/analyses/<id>/reassign - Reassign analysis to different user
- GET /api/admin/users/search - Search users for autocomplete
- POST /api/admin/users/<id>/promote - Promote to admin (owner only)
- POST /api/admin/users/<id>/demote - Demote to user (owner only)
- POST /api/admin/users/<id>/deactivate - Deactivate user (owner only)
"""

from __future__ import annotations
from flask import Blueprint, request, jsonify
from sqlalchemy import desc

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api import get_db
from api.auth_utils import (
    require_admin,
    require_owner,
    is_last_admin,
    _audit_log
)
from models import User, AuditLog, Analysis

admin_bp = Blueprint("admin", __name__)


# ============================================================================
# User Approval Management
# ============================================================================

@admin_bp.get("/pending-users")
@require_admin
def get_pending_users():
    """
    Get list of users awaiting approval.

    Query params:
    - limit (default 100, max 500)

    Returns:
    - 200: {users: [{id, username, created_at}, ...]}
    """
    with get_db() as db:
        limit = min(int(request.args.get("limit", 100)), 500)

        users = db.query(User).filter(
            User.pending_approval == True
        ).order_by(desc(User.created_at)).limit(limit).all()

        return jsonify(users=[{
            "id": u.id,
            "username": u.username,
            "created_at": u.created_at.isoformat()
        } for u in users]), 200


@admin_bp.post("/users/<int:user_id>/approve")
@require_admin
def approve_user(user_id: int):
    """
    Approve pending user.

    Sets active=True, pending_approval=False.
    Logs action to audit trail.

    Returns:
    - 200: {message, user_id}
    - 404: User not found
    - 400: User not pending
    """
    with get_db() as db:
        user = db.query(User).get(user_id)
        if not user:
            return jsonify(error="not_found"), 404

        if not user.pending_approval:
            return jsonify(error="user_not_pending"), 400

        user.active = True
        user.pending_approval = False

        _audit_log(db, "user_approved", details={"target_user_id": user_id, "username": user.username})
        db.commit()

        return jsonify(message="User approved", user_id=user_id), 200


@admin_bp.post("/users/<int:user_id>/reject")
@require_admin
def reject_user(user_id: int):
    """
    Reject pending user with HARD DELETE.

    Frees username for re-signup.
    Guards against deleting users with data.

    Returns:
    - 200: {message, username}
    - 404: User not found
    - 400: User not pending
    - 409: User has analyses (cannot delete)
    """
    with get_db() as db:
        user = db.query(User).get(user_id)
        if not user:
            return jsonify(error="not_found"), 404

        if not user.pending_approval:
            return jsonify(error="user_not_pending"), 400

        # GUARD: Ensure user has no data before hard delete
        has_analyses = db.query(Analysis.id).filter(Analysis.user_id == user_id).first()
        if has_analyses:
            return jsonify(error="user_has_data"), 409

        username = user.username
        _audit_log(db, "user_rejected", details={"target_user_id": user_id, "username": username})

        db.delete(user)  # HARD DELETE (frees username)
        db.commit()

        return jsonify(message="User rejected", username=username), 200


# ============================================================================
# Audit Logs
# ============================================================================

@admin_bp.get("/audit-logs")
@require_admin
def get_audit_logs():
    """
    Get audit logs with username JOIN (N+1 prevention).

    Query params:
    - limit (default 100, max 500)
    - offset (default 0)
    - user_id (optional filter)

    Returns:
    - 200: {logs: [{id, user_id, username, event, ip, user_agent, details, created_at}, ...], total}
    """
    with get_db() as db:
        limit = min(int(request.args.get("limit", 100)), 500)
        offset = int(request.args.get("offset", 0))
        user_id_filter = request.args.get("user_id")

        # JOIN to get username in one query (avoid N+1)
        query = db.query(AuditLog, User.username).outerjoin(
            User, AuditLog.user_id == User.id
        )

        if user_id_filter:
            query = query.filter(AuditLog.user_id == int(user_id_filter))

        total = query.count()
        results = query.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset).all()

        logs = [{
            "id": log.id,
            "user_id": log.user_id,
            "username": username,
            "event": log.event,
            "ip": log.ip,
            "user_agent": log.user_agent,
            "details": log.details_json,
            "created_at": log.created_at.isoformat()
        } for log, username in results]

        return jsonify(logs=logs, total=total, limit=limit, offset=offset), 200


# ============================================================================
# Analysis Management
# ============================================================================

@admin_bp.get("/analyses")
@require_admin
def get_all_analyses():
    """
    Get all analyses with username JOIN (N+1 prevention).

    Query params:
    - limit (default 50, max 500)
    - offset (default 0)
    - user_id (optional filter)
    - status (optional filter)

    Returns:
    - 200: {analyses: [{id, user_id, username, status, created_at, updated_at}, ...], total}
    """
    with get_db() as db:
        limit = min(int(request.args.get("limit", 50)), 500)
        offset = int(request.args.get("offset", 0))
        user_id_filter = request.args.get("user_id")
        status_filter = request.args.get("status")

        # JOIN to avoid N+1
        query = db.query(Analysis, User.username).join(
            User, Analysis.user_id == User.id
        )

        if user_id_filter:
            query = query.filter(Analysis.user_id == int(user_id_filter))
        if status_filter:
            query = query.filter(Analysis.status == status_filter)

        total = query.count()
        results = query.order_by(desc(Analysis.created_at)).limit(limit).offset(offset).all()

        analyses = [{
            "id": a.id,
            "user_id": a.user_id,
            "username": username,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat()
        } for a, username in results]

        return jsonify(analyses=analyses, total=total, limit=limit, offset=offset), 200


@admin_bp.post("/analyses/<analysis_id>/reassign")
@require_admin
def reassign_analysis(analysis_id: str):
    """
    Reassign analysis to different user.

    Request body:
    - {new_user_id: int}

    Validates:
    - Target user exists, is active, and not pending approval

    Returns:
    - 200: {message, analysis_id, new_user_id}
    - 400: Missing new_user_id or invalid target
    - 404: Analysis not found
    """
    with get_db() as db:
        body = request.get_json() or {}
        new_user_id = body.get("new_user_id")

        if not new_user_id:
            return jsonify(error="new_user_id required"), 400

        # Validate analysis exists
        analysis = db.query(Analysis).get(analysis_id)
        if not analysis:
            return jsonify(error="analysis_not_found"), 404

        # Validate target user
        target_user = db.query(User).get(new_user_id)
        if not target_user or not target_user.active or target_user.pending_approval:
            return jsonify(error="invalid_target_user"), 400

        old_user_id = analysis.user_id
        analysis.user_id = new_user_id

        _audit_log(db, "analysis_reassigned", details={
            "analysis_id": analysis_id,
            "old_user_id": old_user_id,
            "new_user_id": new_user_id
        })

        db.commit()

        return jsonify(
            message="Analysis reassigned",
            analysis_id=analysis_id,
            new_user_id=new_user_id
        ), 200


@admin_bp.get("/users/search")
@require_admin
def search_users():
    """
    Search users by username for autocomplete dropdown.

    Query params:
    - q (search term, required, min 1 char)
    - limit (default 20, max 100)

    Only returns active, approved users.

    Returns:
    - 200: {users: [{id, username}, ...]}
    """
    with get_db() as db:
        query = request.args.get("q", "").strip().lower()
        limit = min(int(request.args.get("limit", 20)), 100)

        # Build base query for active, approved users
        base_query = db.query(User).filter(
            User.active == True,
            User.pending_approval == False
        )

        # Apply username filter if query is provided
        if query:
            base_query = base_query.filter(User.username.ilike(f"%{query}%"))

        users = base_query.limit(limit).all()

        return jsonify(users=[{
            "id": u.id,
            "username": u.username,
            "role": u.role
        } for u in users]), 200


# ============================================================================
# Owner-Only: Role Management
# ============================================================================

@admin_bp.post("/users/<int:user_id>/promote")
@require_owner
def promote_to_admin(user_id: int):
    """
    Promote user to admin role (owner only).

    Returns:
    - 200: {message, user_id}
    - 404: User not found
    - 400: Already admin
    - 403: Cannot modify owner
    """
    with get_db() as db:
        user = db.query(User).get(user_id)
        if not user:
            return jsonify(error="not_found"), 404

        if user.role == "admin":
            return jsonify(error="already_admin"), 400

        if user.role == "owner":
            return jsonify(error="cannot_modify_owner"), 403

        user.role = "admin"

        _audit_log(db, "user_promoted", details={"target_user_id": user_id, "username": user.username})
        db.commit()

        return jsonify(message="User promoted to admin", user_id=user_id), 200


@admin_bp.post("/users/<int:user_id>/demote")
@require_owner
def demote_to_user(user_id: int):
    """
    Demote admin to user role (owner only).

    Guards:
    - Cannot demote owner
    - Cannot demote last admin

    Returns:
    - 200: {message, user_id}
    - 404: User not found
    - 400: Already user
    - 403: Cannot modify owner
    - 409: Cannot demote last admin
    """
    with get_db() as db:
        user = db.query(User).get(user_id)
        if not user:
            return jsonify(error="not_found"), 404

        if user.role == "user":
            return jsonify(error="already_user"), 400

        if user.role == "owner":
            return jsonify(error="cannot_modify_owner"), 403

        # GUARD: Don't demote last admin
        if is_last_admin(db, user):
            return jsonify(error="cannot_demote_last_admin"), 409

        user.role = "user"

        _audit_log(db, "user_demoted", details={"target_user_id": user_id, "username": user.username})
        db.commit()

        return jsonify(message="User demoted to user", user_id=user_id), 200


@admin_bp.post("/users/<int:user_id>/deactivate")
@require_owner
def deactivate_user(user_id: int):
    """
    Deactivate user (owner only).

    Guards:
    - Cannot deactivate owner
    - Cannot deactivate last admin

    Returns:
    - 200: {message, user_id}
    - 404: User not found
    - 403: Cannot deactivate owner
    - 409: Cannot deactivate last admin
    """
    with get_db() as db:
        user = db.query(User).get(user_id)
        if not user:
            return jsonify(error="not_found"), 404

        if user.role == "owner":
            return jsonify(error="cannot_deactivate_owner"), 403

        # GUARD: Don't deactivate last admin
        if is_last_admin(db, user):
            return jsonify(error="cannot_deactivate_last_admin"), 409

        user.active = False

        _audit_log(db, "user_deactivated", details={"target_user_id": user_id, "username": user.username})
        db.commit()

        return jsonify(message="User deactivated", user_id=user_id), 200
