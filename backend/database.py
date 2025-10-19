"""
Compatibility shim for legacy imports expecting a top-level `database` module.

Historically parts of the codebase imported `get_db` from `database.py`.
The newer architecture centralizes database helpers inside `api/__init__.py`.
This module re-exports the modern helper so legacy modules (e.g. cleanup jobs)
continue to function without circular imports or ModuleNotFoundError issues.
"""

from api import get_db  # type: ignore F401

__all__ = ["get_db"]
