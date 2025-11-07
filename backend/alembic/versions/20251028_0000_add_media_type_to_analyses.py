"""add_media_type_to_analyses

Revision ID: add_media_type_001
Revises: 2a39d1f230d8
Create Date: 2025-10-28 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_media_type_001"
down_revision = "2a39d1f230d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add media_type column to analyses table with default 'video'
    op.add_column("analyses", sa.Column("media_type", sa.String(length=50), nullable=False, server_default="video"))


def downgrade() -> None:
    # Remove media_type column from analyses table
    op.drop_column("analyses", "media_type")
