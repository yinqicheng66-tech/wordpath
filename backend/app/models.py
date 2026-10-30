"""Database tables.

Shared word data (words, word_books) is kept separate from per-user memory
state (cards). Every answer is appended to review_logs; stats are computed
from the logs.
"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.srs import CardState  # the scheduler owns the list of states


class QuizType(str, enum.Enum):
    meaning = "meaning"
    spelling = "spelling"
    listening = "listening"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Toronto")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(64), unique=True)
    phonetic: Mapped[Optional[str]] = mapped_column(String(128))
    translation: Mapped[str] = mapped_column(Text)
    frq: Mapped[Optional[int]] = mapped_column(Integer)


class WordBook(Base):
    __tablename__ = "word_books"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)


class BookWord(Base):
    __tablename__ = "book_words"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("word_books.id", ondelete="CASCADE"), primary_key=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)


class UserBook(Base):
    __tablename__ = "user_books"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("word_books.id", ondelete="CASCADE"), primary_key=True
    )
    daily_new_limit: Mapped[int] = mapped_column(Integer, default=20)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Card(Base):
    """One user's FSRS memory state for one word."""

    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_cards_user_word"),
        Index("ix_cards_user_due", "user_id", "due_at"),
        Index("ix_cards_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))
    state: Mapped[CardState] = mapped_column(
        Enum(CardState, name="card_state"), default=CardState.new
    )
    step: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    # Empty until the first review; then maintained by app.srs.Scheduler.
    stability: Mapped[Optional[float]] = mapped_column(Float)
    difficulty: Mapped[Optional[float]] = mapped_column(Float)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    # When the word was first shown to this user; used for the daily new-word limit.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReviewLog(Base):
    """One answered question. Append-only."""

    __tablename__ = "review_logs"
    __table_args__ = (Index("ix_review_logs_card_time", "card_id", "reviewed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    quiz_type: Mapped[QuizType] = mapped_column(Enum(QuizType, name="quiz_type"))
    rating: Mapped[int] = mapped_column(SmallInteger)  # 1=again 2=hard 3=good 4=easy
    is_correct: Mapped[bool] = mapped_column(Boolean)
    response_ms: Mapped[Optional[int]] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
