"""user_books: mark the active book explicitly

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_books",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Until now the most recently started book was the active one.
    op.execute(
        """
        UPDATE user_books SET is_active = TRUE
        WHERE (user_id, started_at) IN (
            SELECT user_id, MAX(started_at) FROM user_books GROUP BY user_id
        )
        """
    )


def downgrade() -> None:
    op.drop_column("user_books", "is_active")
