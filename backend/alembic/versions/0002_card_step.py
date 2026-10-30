"""cards: add learning step; stability and difficulty empty until first review

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("step", sa.Integer(), nullable=True))
    op.alter_column("cards", "stability", existing_type=sa.Float(), nullable=True)
    op.alter_column("cards", "difficulty", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE cards SET stability = 0 WHERE stability IS NULL")
    op.execute("UPDATE cards SET difficulty = 0 WHERE difficulty IS NULL")
    op.alter_column("cards", "difficulty", existing_type=sa.Float(), nullable=False)
    op.alter_column("cards", "stability", existing_type=sa.Float(), nullable=False)
    op.drop_column("cards", "step")
