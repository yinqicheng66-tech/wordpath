"""initial schema: users, words, word books, cards, review logs

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

card_state = sa.Enum("new", "learning", "review", "relearning", name="card_state")
quiz_type = sa.Enum("meaning", "spelling", "listening", name="quiz_type")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "words",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("word", sa.String(64), nullable=False, unique=True),
        sa.Column("phonetic", sa.String(128), nullable=True),
        sa.Column("translation", sa.Text(), nullable=False),
        sa.Column("frq", sa.Integer(), nullable=True),
    )
    op.create_table(
        "word_books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "book_words",
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("word_books.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "word_id",
            sa.Integer(),
            sa.ForeignKey("words.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_table(
        "user_books",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("word_books.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("daily_new_limit", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "word_id",
            sa.Integer(),
            sa.ForeignKey("words.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", card_state, nullable=False),
        sa.Column("stability", sa.Float(), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.UniqueConstraint("user_id", "word_id", name="uq_cards_user_word"),
    )
    op.create_index("ix_cards_user_due", "cards", ["user_id", "due_at"])
    op.create_table(
        "review_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "card_id",
            sa.Integer(),
            sa.ForeignKey("cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quiz_type", quiz_type, nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_review_logs_card_time", "review_logs", ["card_id", "reviewed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_review_logs_card_time", table_name="review_logs")
    op.drop_table("review_logs")
    op.drop_index("ix_cards_user_due", table_name="cards")
    op.drop_table("cards")
    op.drop_table("user_books")
    op.drop_table("book_words")
    op.drop_table("word_books")
    op.drop_table("words")
    op.drop_table("users")
    quiz_type.drop(op.get_bind(), checkfirst=True)
    card_state.drop(op.get_bind(), checkfirst=True)
