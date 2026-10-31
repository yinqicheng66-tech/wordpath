"""Importer tests run against in-memory SQLite, so they need no Postgres."""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.importer import import_all_books, import_words
from app.models import BookWord, Word, WordBook
from app.wordbank import BOOKS, WordEntry


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


TAGGED = [
    WordEntry("state", "steit", "n. 州，状态", 137, ("cet4", "gk", "zk")),
    WordEntry("might", "mait", "aux. 可能，也许", 175, ("cet4", "gk")),
    WordEntry("ubiquitous", None, "a. 无所不在的", None, ("gre",)),
]


def book_contents(session, name):
    return session.scalars(
        select(Word.word)
        .join(BookWord, BookWord.word_id == Word.id)
        .join(WordBook, WordBook.id == BookWord.book_id)
        .where(WordBook.name == name)
        .order_by(BookWord.position)
    ).all()


def test_import_all_books_shares_words_between_books(session):
    books = import_all_books(session, TAGGED)

    assert len(books) == len(BOOKS)
    assert count(session, Word) == 3  # each word stored once
    assert book_contents(session, "中考词汇") == ["state"]
    # "state" is also a 中考 word, so the 高考 book shows it after "might"
    assert book_contents(session, "高考词汇") == ["might", "state"]
    assert book_contents(session, "GRE 词汇") == ["ubiquitous"]
    # the starter book only takes words with frequency data
    assert book_contents(session, "四级高频 1000") == ["state", "might"]


def test_import_all_books_renames_the_old_core_book(session):
    old = import_words(session, ENTRIES, book_name="核心 1000 词")
    import_all_books(session, TAGGED)

    assert old.name == "四级高频 1000"
    assert session.scalar(select(WordBook).where(WordBook.name == "核心 1000 词")) is None
    assert count(session, WordBook) == len(BOOKS)


def test_import_uses_few_database_round_trips(session):
    """The production database is across the network, where every round trip
    costs ~10 ms. Row-by-row inserts of ~58k rows once timed out the deploy."""
    from sqlalchemy import event

    entries = [
        WordEntry(f"word{i}", None, f"n. 词{i}", i + 1, ("cet4", "gk", "zk"))
        for i in range(2000)
    ]
    calls = {"n": 0}

    def count(conn, cursor, statement, params, context, executemany):
        calls["n"] += len(params) if executemany else 1

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", count)
    try:
        import_all_books(session, entries)
        first = calls["n"]
        calls["n"] = 0
        import_all_books(session, entries)  # nothing changed
        again = calls["n"]
    finally:
        event.remove(engine, "before_cursor_execute", count)

    assert first < 100  # ~6,000 rows written in batches
    assert again < 50  # unchanged data is only read
