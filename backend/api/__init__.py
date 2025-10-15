"""
api package: DB engine/session + password hashing utilities.

This module must not contain route/business logic.

Public API:
- init_engine(db_url: str) -> None
- get_db() -> context manager / generator yielding Session
- hash_password(plain: str) -> str
- verify_password(hash: str, plain: str) -> bool
"""

from __future__ import annotations
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None
_ph = PasswordHasher()


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models (define in routes for now; move later)."""
    pass


def engine() -> Engine:
    assert _engine is not None, "init_engine() must be called first"
    return _engine


def init_engine(db_url: str) -> None:
    """
    Initialize global Engine + SessionLocal once per process.
    - db_url: e.g., "sqlite:///instance/app.db"
    """
    global _engine, _SessionLocal
    if _engine is not None:
        return  # already initialized
    # SQLite: check_same_thread False for Flask threaded server
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    _engine = create_engine(db_url, future=True, pool_pre_ping=True, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    # NOTE: do NOT create tables here; Alembic migrations will handle it later.


@contextmanager
def get_db() -> Iterator[Session]:
    """
    Yields a SQLAlchemy Session and guarantees close() at exit.
    Automatically commits on success, rolls back on exception.

    Usage:
        with get_db() as db:
            ...
            # commit happens automatically on successful exit
    """
    assert _SessionLocal is not None, "init_engine() must be called before get_db()"
    db = _SessionLocal()
    try:
        yield db
        db.commit()  # Auto-commit on success
    except Exception:
        db.rollback()  # Auto-rollback on exception
        raise
    finally:
        db.close()


def hash_password(plain: str) -> str:
    """
    Return Argon2 hash string for a plaintext password.
    TODO: call _ph.hash(plain) and return it.
    """
    # reject empty passwords at the helper level
    if not isinstance(plain, str) or not plain:
        raise ValueError("empty password")
    return _ph.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    """
    Verify plaintext against Argon2 hash. Return True/False.
    TODO: call _ph.verify(stored_hash, plain); catch exceptions and return False on failure.
    """
    try:
        _ph.verify(stored_hash, plain)
        return True
    except (VerifyMismatchError, InvalidHash, Exception):
        return False