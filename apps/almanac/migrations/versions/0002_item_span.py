"""item end and whole-day flag

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("end_at", sa.DateTime(), nullable=True))
    op.add_column("items", sa.Column("all_day", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("items", "all_day")
    op.drop_column("items", "end_at")
