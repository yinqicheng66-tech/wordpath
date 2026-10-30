"""Model tests run against in-memory SQLite, so they need no Postgres."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Card, CardState, User, Word


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def make_user_and_word(session):
    user = User(email="a@example.com", password_hash="x")
    word = Word(word="apple", translation="n. 苹果")
    session.add_all([user, word])
    session.flush()
    return user, word


def test_new_card_defaults(session):
    user, word = make_user_and_word(session)
    card = Card(user_id=user.id, word_id=word.id, due_at=datetime.now(timezone.utc))
    session.add(card)
    session.flush()

    assert card.state == CardState.new
    assert card.reps == 0
    assert card.lapses == 0


def test_one_card_per_user_and_word(session):
    user, word = make_user_and_word(session)
    now = datetime.now(timezone.utc)
    session.add(Card(user_id=user.id, word_id=word.id, due_at=now))
    session.flush()

    session.add(Card(user_id=user.id, word_id=word.id, due_at=now))
    with pytest.raises(IntegrityError):
        session.flush()


def test_email_is_unique(session):
    session.add(User(email="a@example.com", password_hash="x"))
    session.flush()
    session.add(User(email="a@example.com", password_hash="y"))
    with pytest.raises(IntegrityError):
        session.flush()
