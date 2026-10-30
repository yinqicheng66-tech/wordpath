"""Importer tests run against in-memory SQLite, so they need no Postgres."""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.importer import import_words
from app.models import BookWord, Word, WordBook
from app.wordbank import WordEntry


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


ENTRIES = [
    WordEntry("state", "steit", "n. 州，状态", 137),
    WordEntry("might", "mait", "aux. 可能，也许", 175),
]


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_import_creates_words_and_ordered_book(session):
    book = import_words(session, ENTRIES)

    assert count(session, Word) == 2
    positions = session.execute(
        select(Word.word, BookWord.position)
        .join(BookWord, BookWord.word_id == Word.id)
        .where(BookWord.book_id == book.id)
        .order_by(BookWord.position)
    ).all()
    assert positions == [("state", 1), ("might", 2)]


def test_import_twice_does_not_duplicate(session):
    import_words(session, ENTRIES)
    import_words(session, ENTRIES)

    assert count(session, Word) == 2
    assert count(session, WordBook) == 1
    assert count(session, BookWord) == 2


def test_reimport_updates_translation(session):
    import_words(session, ENTRIES)
    import_words(session, [WordEntry("state", "steit", "n. 状态", 137)])

    state = session.scalar(select(Word).where(Word.word == "state"))
    assert state.translation == "n. 状态"
    # the book now only lists the words from the latest import
    assert count(session, BookWord) == 1
