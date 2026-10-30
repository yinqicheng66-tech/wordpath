"""Build the core word list from the ECDICT dictionary.

ECDICT (https://github.com/skywind3000/ECDICT, MIT License) has ~770k
entries. This module picks the most frequent CET-4 words and cleans their
Chinese translations so they fit on a flashcard.

Everything here is pure Python (no database), so it is easy to test.
"""
import csv
import re
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional

# Some ECDICT phonetics use the Cyrillic letter "ә" instead of the IPA schwa "ə".
_PHONETIC_FIXES = {"ә": "ə"}

# Meanings within one part of speech are separated by commas or semicolons.
_MEANING_SPLIT = re.compile(r"\s*[,，;；]\s*")
# A line such as "n. 苹果, 家伙" starts with a part-of-speech label.
_POS_PREFIX = re.compile(r"^([a-z]+\.)\s*(.*)$")

MAX_POS_LINES = 3
MAX_MEANINGS_PER_LINE = 4


@dataclass(frozen=True)
class WordEntry:
    word: str
    phonetic: Optional[str]
    translation: str
    frq: int


def normalize_phonetic(phonetic: str) -> Optional[str]:
    phonetic = phonetic.strip()
    if not phonetic:
        return None
    for wrong, right in _PHONETIC_FIXES.items():
        phonetic = phonetic.replace(wrong, right)
    return phonetic


def clean_translation(raw: str) -> str:
    """Keep the first few parts of speech and the first few meanings of each.

    "n. 州, 状态, 情形, 国家, 政府\\na. 国家的\\n[计] 状态"
    becomes "n. 州，状态，情形，国家\\na. 国家的".
    Domain-specific lines such as "[计]", "[医]" and "[网络]" are dropped.
    """
    # ECDICT stores line breaks as the two characters backslash + "n".
    lines = raw.replace("\\n", "\n").split("\n")
    kept: List[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("["):
            continue
        match = _POS_PREFIX.match(line)
        pos, body = (match.group(1), match.group(2)) if match else ("", line)
        meanings = [m for m in _MEANING_SPLIT.split(body) if m]
        if not meanings:
            continue
        text = "，".join(meanings[:MAX_MEANINGS_PER_LINE])
        kept.append(f"{pos} {text}" if pos else text)
        if len(kept) == MAX_POS_LINES:
            break
    return "\n".join(kept)


def _is_plain_word(word: str) -> bool:
    """Single lowercase English word: no phrases, abbreviations or proper nouns."""
    return word.isascii() and word.isalpha() and word.islower()


def select_words(
    rows: Iterable[dict], tag: str = "cet4", limit: int = 1000
) -> List[WordEntry]:
    """Return the `limit` most frequent words carrying `tag`, cleaned."""
    candidates = []
    for row in rows:
        word = row["word"].strip()
        if not _is_plain_word(word):
            continue
        if tag not in row.get("tag", "").split():
            continue
        try:
            frq = int(row.get("frq") or 0)
        except ValueError:
            continue
        if frq <= 0:  # 0 means "no frequency data"
            continue
        translation = clean_translation(row.get("translation", ""))
        if not translation:
            continue
        candidates.append(
            WordEntry(
                word=word,
                phonetic=normalize_phonetic(row.get("phonetic", "")),
                translation=translation,
                frq=frq,
            )
        )
    candidates.sort(key=lambda e: (e.frq, e.word))
    return candidates[:limit]


def read_ecdict(path: str) -> Iterator[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


WORDLIST_FIELDS = ["word", "phonetic", "translation", "frq"]


def write_wordlist(entries: Iterable[WordEntry], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=WORDLIST_FIELDS)
        writer.writeheader()
        for e in entries:
            writer.writerow(
                {
                    "word": e.word,
                    "phonetic": e.phonetic or "",
                    "translation": e.translation,
                    "frq": e.frq,
                }
            )


def read_wordlist(path: str) -> List[WordEntry]:
    with open(path, encoding="utf-8", newline="") as f:
        return [
            WordEntry(
                word=row["word"],
                phonetic=row["phonetic"] or None,
                translation=row["translation"],
                frq=int(row["frq"]),
            )
            for row in csv.DictReader(f)
        ]
