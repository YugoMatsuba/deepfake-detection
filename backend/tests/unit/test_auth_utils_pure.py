"""
Tests for auth_utils helper functions.

Tests database query functions and business logic from api/auth_utils.py
that don't require Flask request context.
"""

from api.auth_utils import (
    count_active_admins,
    is_last_admin
)
from api import get_db
from models import User


class TestCountActiveAdmins:
    """Test count_active_admins database query."""

    def test_counts_multiple_active_admins(self):
        """Count multiple active admins and owners."""
        with get_db() as db:
            # Create active admin
            admin1 = User(username="admin1", password_hash="hash1", role="admin", active=True)
            db.add(admin1)

            # Create active owner
            owner = User(username="owner1", password_hash="hash2", role="owner", active=True)
            db.add(owner)

            # Create regular user (should not be counted)
            user = User(username="user1", password_hash="hash3", role="user", active=True)
            db.add(user)

            db.commit()

            count = count_active_admins(db)
            assert count == 2  # admin1 + owner1

    def test_excludes_inactive_admins(self):
        """Do not count inactive admins."""
        with get_db() as db:
            # Active admin
            admin1 = User(username="admin_active", password_hash="hash1", role="admin", active=True)
            db.add(admin1)

            # Inactive admin (should not be counted)
            admin2 = User(username="admin_inactive", password_hash="hash2", role="admin", active=False)
            db.add(admin2)

            db.commit()

            count = count_active_admins(db)
            assert count == 1  # Only admin_active

    def test_returns_zero_when_no_admins(self):
        """Return 0 when no admins exist."""
        with get_db() as db:
            # Only regular users
            user = User(username="user1", password_hash="hash1", role="user", active=True)
            db.add(user)
            db.commit()

            count = count_active_admins(db)
            assert count == 0

    def test_counts_only_admin_and_owner_roles(self):
        """Count only users with admin or owner roles."""
        with get_db() as db:
            # Admin
            admin = User(username="admin", password_hash="hash1", role="admin", active=True)
            db.add(admin)

            # Owner
            owner = User(username="owner", password_hash="hash2", role="owner", active=True)
            db.add(owner)

            # Regular users (should not be counted)
            user1 = User(username="user1", password_hash="hash3", role="user", active=True)
            user2 = User(username="user2", password_hash="hash4", role="user", active=True)
            db.add(user1)
            db.add(user2)

            db.commit()

            count = count_active_admins(db)
            assert count == 2  # admin + owner


class TestIsLastAdmin:
    """Test is_last_admin business logic."""

    def test_returns_true_when_last_active_admin(self):
        """Return True when user is the only active admin."""
        with get_db() as db:
            # Single active admin
            admin = User(username="last_admin", password_hash="hash1", role="admin", active=True)
            db.add(admin)

            # Inactive admin (doesn't count)
            inactive_admin = User(username="inactive", password_hash="hash2", role="admin", active=False)
            db.add(inactive_admin)

            # Regular user (doesn't count)
            user = User(username="user1", password_hash="hash3", role="user", active=True)
            db.add(user)

            db.commit()

            assert is_last_admin(db, admin) is True

    def test_returns_false_when_multiple_admins_exist(self):
        """Return False when multiple active admins exist."""
        with get_db() as db:
            # Two active admins
            admin1 = User(username="admin1", password_hash="hash1", role="admin", active=True)
            admin2 = User(username="admin2", password_hash="hash2", role="admin", active=True)
            db.add(admin1)
            db.add(admin2)

            db.commit()

            assert is_last_admin(db, admin1) is False
            assert is_last_admin(db, admin2) is False

    def test_returns_false_for_inactive_admin(self):
        """Return False for inactive admin even if they're the only admin."""
        with get_db() as db:
            # Inactive admin
            admin = User(username="admin", password_hash="hash1", role="admin", active=False)
            db.add(admin)

            db.commit()

            assert is_last_admin(db, admin) is False

    def test_returns_false_for_regular_user(self):
        """Return False for regular users (not admin/owner)."""
        with get_db() as db:
            # Regular user
            user = User(username="user", password_hash="hash1", role="user", active=True)
            db.add(user)

            # Admin exists
            admin = User(username="admin", password_hash="hash2", role="admin", active=True)
            db.add(admin)

            db.commit()

            assert is_last_admin(db, user) is False

    def test_returns_true_for_last_owner(self):
        """Return True when user is the only active owner."""
        with get_db() as db:
            # Single active owner
            owner = User(username="owner", password_hash="hash1", role="owner", active=True)
            db.add(owner)

            # Regular users (don't count)
            user1 = User(username="user1", password_hash="hash2", role="user", active=True)
            user2 = User(username="user2", password_hash="hash3", role="user", active=True)
            db.add(user1)
            db.add(user2)

            db.commit()

            assert is_last_admin(db, owner) is True

    def test_returns_false_when_admin_and_owner_both_exist(self):
        """Return False when both active admin and owner exist."""
        with get_db() as db:
            # Active admin
            admin = User(username="admin", password_hash="hash1", role="admin", active=True)
            db.add(admin)

            # Active owner
            owner = User(username="owner", password_hash="hash2", role="owner", active=True)
            db.add(owner)

            db.commit()

            # Neither is the "last" admin since both exist
            assert is_last_admin(db, admin) is False
            assert is_last_admin(db, owner) is False
