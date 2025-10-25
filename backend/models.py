"""
Consolidated SQLAlchemy models for the deepfake detection backend.

All models use the shared Base from api package and follow SQLAlchemy 2.0 patterns.
Alembic migrations reference this file as the source of truth for schema.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum, ForeignKey, Index, text, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from api import Base


# ============================================================================
# Auth Models (migrated from api/routes/auth.py for Alembic)
# ============================================================================

class User(Base):
    """
    User account for authentication and authorization.

    Roles:
    - user: normal usage (pending approval by default)
    - admin: can approve users, view all data, reassign analyses
    - owner: single super-admin, can promote/demote admins (env-enforced)
    """
    __tablename__ = "users"

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_users_pending_created', 'pending_approval', 'created_at'),
        Index('ix_users_active_role', 'active', 'role'),
        CheckConstraint("role IN ('user', 'admin', 'owner')", name='ck_user_role'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Role as String for portability (avoids Enum ALTER TYPE headaches)
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="user",
        server_default="user"
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true")
    )

    # New field: approval workflow
    pending_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class AuditLog(Base):
    """
    Audit trail for authentication and admin events.

    Captures: login, logout, signup, approval, rejection, reassignment, etc.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )
    event: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # New field: structured details for admin actions
    details_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )


# ============================================================================
# Analysis Models
# ============================================================================

class Analysis(Base):
    """
    Video analysis tracking and results storage.

    Lifecycle:
    1. Created on upload → status="created"
    2. Analysis started → status="running"
    3. Analysis complete → status="succeeded", result_json populated
    4. Analysis failed → status="failed", error populated

    Security:
    - video_path is absolute server path, NEVER exposed to client
    - Access controlled via user_id ownership check

    Storage:
    - result_json contains ONLY scores/metadata (no base64 images)
    - Base64 overlays sent in HTTP response but NOT persisted to DB
    """
    __tablename__ = "analyses"

    # Composite indexes for admin dashboard queries
    __table_args__ = (
        Index('ix_analyses_user_created', 'user_id', 'created_at'),
        Index('ix_analyses_status_created', 'status', 'created_at'),
    )

    # Primary key (UUID for external references)
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False
    )

    # Foreign key to user (for ownership/auth)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(16),
        CheckConstraint("status IN ('created', 'running', 'succeeded', 'failed')", name='ck_analysis_status'),
        nullable=False,
        default="created",
        server_default="created",
        index=True
    )

    # Video metadata (server-only, never exposed to client)
    video_path: Mapped[str] = mapped_column(Text, nullable=False)
    video_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # JSON payloads
    meta_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}"
    )  # Contains: {schema_version, device, code_commit, fps, frame_count, width, height}

    result_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}"
    )  # Contains: SCORES ONLY (no base64 images) - {ml: {...}, traditional: {...}}

    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
