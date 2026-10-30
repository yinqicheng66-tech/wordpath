"""Load the core word list into the database.

Usage (from the backend folder, with the virtualenv active):

    python -m app.importer                     # load data/core_1000.csv
    python -m app.importer --from-ecdict ecdict.csv
                                               # rebuild the list from ECDICT first

Running it again is safe: existing words are updated, not duplicated.
"""
import argparse
from pathlib import Path
from typing import List

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import BookWord, Word, WordBook
from app.wordbank import (
    WordEntry,
    read_ecdict,
    read_wordlist,
    select_words,
    write_wordlist,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_WORDLIST = DATA_DIR / "core_1000.csv"
BOOK_NAME = "核心 1000 词"
BOOK_DESCRIPTION = "四级词汇中最常用的 1000 个单词，按词频排序。数据来自 ECDICT（MIT 许可）。"


def import_words(
    session: Session,
    entries: List[WordEntry],
    book_name: str = BOOK_NAME,
    book_description: str = BOOK_DESCRIPTION,
) -> WordBook:
    """Upsert words and (re)build the word book's ordered word list."""
    existing = {
        w.word: w
        for w in session.scalars(
            select(Word).where(Word.word.in_([e.word for e in entries]))
        )
    }
    words: List[Word] = []
    for e in entries:
        word = existing.get(e.word)
        if word is None:
            word = Word(word=e.word)
            session.add(word)
        word.phonetic = e.phonetic
        word.translation = e.translation
        word.frq = e.frq
        words.append(word)

    book = session.scalar(select(WordBook).where(WordBook.name == book_name))
    if book is None:
        book = WordBook(name=book_name)
        session.add(book)
    book.description = book_description
    session.flush()  # assigns ids to new words and the book

    session.execute(delete(BookWord).where(BookWord.book_id == book.id))
    session.add_all(
        BookWord(book_id=book.id, word_id=w.id, position=i)
        for i, w in enumerate(words, start=1)
    )
    session.flush()
    return book


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the core word list.")
    parser.add_argument(
        "--from-ecdict",
        metavar="CSV",
        help="rebuild data/core_1000.csv from an ECDICT ecdict.csv first",
    )
    args = parser.parse_args()

    if args.from_ecdict:
        entries = select_words(read_ecdict(args.from_ecdict))
        write_wordlist(entries, str(DEFAULT_WORDLIST))
        print(f"Rebuilt {DEFAULT_WORDLIST.name} with {len(entries)} words")

    entries = read_wordlist(str(DEFAULT_WORDLIST))

    with SessionLocal() as session:
        book = import_words(session, entries)
        session.commit()
        print(f"Imported {len(entries)} words into word book '{book.name}'")


if __name__ == "__main__":
    main()
