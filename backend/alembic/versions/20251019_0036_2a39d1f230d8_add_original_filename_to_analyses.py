"""add_original_filename_to_analyses

Revision ID: 2a39d1f230d8
Revises: 113c95d47e95
Create Date: 2025-10-19 00:36:50.312098

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a39d1f230d8"
down_revision = "113c95d47e95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add original_filename column to analyses table
    op.add_column("analyses", sa.Column("original_filename", sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Remove original_filename column from analyses table
    op.drop_column("analyses", "original_filename")
