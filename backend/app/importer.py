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

from sqlalchemy import delete, func, insert, select, update
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


def upsert_words(session: Session, entries: Iterable[WordEntry]) -> Dict[str, int]:
    """Insert new words and update changed ones. Returns {word text: word id}.

    Written for a database across the network: rows are sent CHUNK at a time
    in one multi-row INSERT, and unchanged words are not written at all, so a
    re-import with nothing new costs only the reads.
    """
    entries = list(entries)
    ids: Dict[str, int] = {}
    current: Dict[str, tuple] = {}
    for chunk in _chunks([e.word for e in entries]):
        rows = session.execute(
            select(Word.id, Word.word, Word.phonetic, Word.translation, Word.frq).where(
                Word.word.in_(chunk)
            )
        )
        for id_, word, phonetic, translation, frq in rows:
            ids[word] = id_
            current[word] = (phonetic, translation, frq)

    new_rows = []
    for e in entries:
        values = (e.phonetic, e.translation, e.frq)
        if e.word not in ids:
            new_rows.append(
                {"word": e.word, "phonetic": e.phonetic, "translation": e.translation, "frq": e.frq}
            )
        elif current[e.word] != values:  # rare: the dictionary data was corrected
            session.execute(
                update(Word)
                .where(Word.id == ids[e.word])
                .values(phonetic=e.phonetic, translation=e.translation, frq=e.frq)
            )

    for chunk in _chunks(new_rows):
        inserted = session.execute(
            insert(Word).values(list(chunk)).returning(Word.id, Word.word)
        )
        for id_, word in inserted:
            ids[word] = id_
    return ids


def build_book(
    session: Session, name: str, description: str, word_ids: List[int]
) -> WordBook:
    """Create or update a book so it lists exactly `word_ids`, in this order."""
    book = session.scalar(select(WordBook).where(WordBook.name == name))
    if book is None:
        book = WordBook(name=name)
        session.add(book)
    book.description = description
    session.flush()

    current = session.scalars(
        select(BookWord.word_id)
        .where(BookWord.book_id == book.id)
        .order_by(BookWord.position)
    ).all()
    if list(current) == list(word_ids):
        return book  # already up to date

    session.execute(delete(BookWord).where(BookWord.book_id == book.id))
    for n, chunk in enumerate(_chunks(word_ids)):
        session.execute(
            insert(BookWord).values(
                [
                    {"book_id": book.id, "word_id": word_id, "position": n * CHUNK + i + 1}
                    for i, word_id in enumerate(chunk)
                ]
            )
        )
    return book


def import_words(
    session: Session,
    entries: List[WordEntry],
    book_name: str = "四级高频 1000",
    book_description: str = "",
) -> WordBook:
    """Import `entries` as a single book, in the given order."""
    ids = upsert_words(session, entries)
    return build_book(session, book_name, book_description, [ids[e.word] for e in entries])


def import_all_books(session: Session, entries: List[WordEntry]) -> List[WordBook]:
    """Import every word and build every book defined in app.wordbank.BOOKS."""
    for old, new in RENAMED_BOOKS.items():
        book = session.scalar(select(WordBook).where(WordBook.name == old))
        taken = session.scalar(select(WordBook).where(WordBook.name == new))
        if book is not None and taken is None:
            book.name = new
    ids = upsert_words(session, entries)
    books = []
    for spec in BOOKS:
        ordered = [ids[e.word] for e in book_words(entries, spec)]
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
