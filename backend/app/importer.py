"""Load the word books into the database.

Usage (from the backend folder, with the virtualenv active):

    python -m app.importer                     # load data/words.csv
    python -m app.importer --from-ecdict ecdict.csv
                                               # rebuild data/words.csv from ECDICT first

Running it again is safe: existing words are updated, not duplicated, and
each book's word list is rebuilt. Users' learning progress is kept.
"""
import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import BookWord, Word, WordBook
from app.wordbank import (
    BOOKS,
    WordEntry,
    book_words,
    extract_entries,
    read_ecdict,
    read_wordlist,
    write_wordlist,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_WORDLIST = DATA_DIR / "words.csv"
CHUNK = 500  # keeps IN (...) lists and insert batches a reasonable size
# Books that were renamed; existing enrollments and progress follow the rename.
RENAMED_BOOKS = {"核心 1000 词": "四级高频 1000"}


def _chunks(items: Sequence, size: int = CHUNK) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def upsert_words(session: Session, entries: Iterable[WordEntry]) -> Dict[str, Word]:
    """Insert new words and update existing ones. Returns {word text: Word}."""
    entries = list(entries)
    existing: Dict[str, Word] = {}
    for chunk in _chunks([e.word for e in entries]):
        for w in session.scalars(select(Word).where(Word.word.in_(chunk))):
            existing[w.word] = w

    words: Dict[str, Word] = {}
    for e in entries:
        word = existing.get(e.word)
        if word is None:
            word = Word(word=e.word)
            session.add(word)
        word.phonetic = e.phonetic
        word.translation = e.translation
        word.frq = e.frq
        words[e.word] = word
    session.flush()  # assigns ids to new words
    return words


def build_book(
    session: Session, name: str, description: str, words: List[Word]
) -> WordBook:
    """Create or update a book so it lists exactly `words`, in this order."""
    book = session.scalar(select(WordBook).where(WordBook.name == name))
    if book is None:
        book = WordBook(name=name)
        session.add(book)
    book.description = description
    session.flush()

    session.execute(delete(BookWord).where(BookWord.book_id == book.id))
    for n, chunk in enumerate(_chunks(words)):
        session.add_all(
            BookWord(book_id=book.id, word_id=w.id, position=n * CHUNK + i + 1)
            for i, w in enumerate(chunk)
        )
        session.flush()
    return book


def import_words(
    session: Session,
    entries: List[WordEntry],
    book_name: str = "四级高频 1000",
    book_description: str = "",
) -> WordBook:
    """Import `entries` as a single book, in the given order."""
    words = upsert_words(session, entries)
    return build_book(
        session, book_name, book_description, [words[e.word] for e in entries]
    )


def import_all_books(session: Session, entries: List[WordEntry]) -> List[WordBook]:
    """Import every word and build every book defined in app.wordbank.BOOKS."""
    for old, new in RENAMED_BOOKS.items():
        book = session.scalar(select(WordBook).where(WordBook.name == old))
        taken = session.scalar(select(WordBook).where(WordBook.name == new))
        if book is not None and taken is None:
            book.name = new
    words = upsert_words(session, entries)
    books = []
    for spec in BOOKS:
        ordered = [words[e.word] for e in book_words(entries, spec)]
        books.append(build_book(session, spec.name, spec.description, ordered))
    return books


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the word books.")
    parser.add_argument(
        "--from-ecdict",
        metavar="CSV",
        help="rebuild data/words.csv from an ECDICT ecdict.csv first",
    )
    args = parser.parse_args()

    if args.from_ecdict:
        entries = extract_entries(read_ecdict(args.from_ecdict))
        write_wordlist(entries, str(DEFAULT_WORDLIST))
        print(f"Rebuilt {DEFAULT_WORDLIST.name} with {len(entries)} words")

    entries = read_wordlist(str(DEFAULT_WORDLIST))

    with SessionLocal() as session:
        books = import_all_books(session, entries)
        session.commit()
        print(f"Imported {len(entries)} words into {len(books)} word books:")
        for book in books:
            count = session.scalar(
                select(func.count()).select_from(BookWord).where(BookWord.book_id == book.id)
            )
            print(f"  {book.name}: {count}")


if __name__ == "__main__":
    main()
