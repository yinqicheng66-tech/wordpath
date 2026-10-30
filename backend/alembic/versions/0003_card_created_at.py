"""cards: record when each word was first introduced

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cards",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_cards_user_created", "cards", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_cards_user_created", table_name="cards")
    op.drop_column("cards", "created_at")
