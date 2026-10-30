"""Build word books from the ECDICT dictionary.

ECDICT (https://github.com/skywind3000/ECDICT, MIT License) has ~770k
entries, ~14.6k of which are tagged with Chinese exam syllabuses
(中考, 高考, CET-4/6, 考研, IELTS, TOEFL, GRE). This module keeps those words,
cleans their Chinese translations so they fit on a flashcard, and defines
which words go into which word book.

Everything here is pure Python (no database), so it is easy to test.
"""
import csv
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

# Some ECDICT phonetics use the Cyrillic letter "ә" instead of the IPA schwa "ə".
_PHONETIC_FIXES = {"ә": "ə"}

# Meanings within one part of speech are separated by commas or semicolons.
_MEANING_SPLIT = re.compile(r"\s*[,，;；]\s*")
# A line such as "n. 苹果, 家伙" starts with a part-of-speech label.
_POS_PREFIX = re.compile(r"^([a-z]+\.)\s*(.*)$")
_DOMAIN_LABEL = re.compile(r"^\[[^\]]*\]\s*")

MAX_POS_LINES = 3
MAX_MEANINGS_PER_LINE = 4


@dataclass(frozen=True)
class WordEntry:
    word: str
    phonetic: Optional[str]
    translation: str
    frq: Optional[int]  # COCA frequency rank (1 = most common); None if unknown
    tags: Tuple[str, ...] = ()  # exam syllabuses this word belongs to


@dataclass(frozen=True)
class BookSpec:
    name: str
    description: str
    tag: str
    limit: Optional[int] = None  # keep only the N most frequent words
    # Words also found in these easier syllabuses go to the back of the book,
    # so e.g. a GRE learner starts with GRE words rather than "want".
    basics: Tuple[str, ...] = ()


_BASICS = ("zk", "gk", "cet4")


# Ordered roughly from easiest to hardest.
BOOKS: Tuple[BookSpec, ...] = (
    BookSpec("四级高频 1000", "四级词汇里最常用的 1000 个，适合起步。", "cet4", 1000),
    BookSpec("中考词汇", "初中英语核心词汇。", "zk"),
    BookSpec("高考词汇", "高中英语课标词汇。", "gk", basics=("zk",)),
    BookSpec("四级词汇", "大学英语四级（CET-4）完整词表。", "cet4", basics=("zk", "gk")),
    BookSpec("六级词汇", "大学英语六级（CET-6）完整词表。", "cet6", basics=_BASICS),
    BookSpec("考研词汇", "全国硕士研究生入学考试英语词汇。", "ky", basics=_BASICS),
    BookSpec("雅思词汇", "IELTS 常考词汇。", "ielts", basics=_BASICS),
    BookSpec("托福词汇", "TOEFL 常考词汇。", "toefl", basics=_BASICS),
    BookSpec("GRE 词汇", "GRE 常考词汇，难度最高。", "gre", basics=_BASICS),
)
EXAM_TAGS = frozenset(b.tag for b in BOOKS)


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
    # ECDICT stores line breaks as the two characters backslash + "n"
    # (sometimes preceded by a literal backslash + "r", or a real carriage return).
    raw = raw.replace("\\r", "").replace("\r", "")
    lines = raw.replace("\\n", "\n").split("\n")
    kept: List[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("["):
            continue
        match = _POS_PREFIX.match(line)
        pos, body = (match.group(1), match.group(2)) if match else ("", line)
        if body.startswith("["):  # e.g. "art. [计] 累加器": a technical sense
            continue
        # drop inline domain labels: "[经] 利益" -> "利益"
        meanings = [_DOMAIN_LABEL.sub("", m) for m in _MEANING_SPLIT.split(body)]
        meanings = [m for m in meanings if m]
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


def _parse_frq(value: Optional[str]) -> Optional[int]:
    try:
        frq = int(value or 0)
    except ValueError:
        return None
    return frq if frq > 0 else None  # 0 means "no frequency data"


def extract_entries(rows: Iterable[dict]) -> List[WordEntry]:
    """Every plain word tagged with at least one exam, cleaned, sorted by word."""
    entries = []
    for row in rows:
        word = row["word"].strip()
        if not _is_plain_word(word):
            continue
        tags = tuple(sorted(t for t in row.get("tag", "").split() if t in EXAM_TAGS))
        if not tags:
            continue
        translation = clean_translation(row.get("translation", ""))
        if not translation:
            continue
        entries.append(
            WordEntry(
                word=word,
                phonetic=normalize_phonetic(row.get("phonetic", "")),
                translation=translation,
                frq=_parse_frq(row.get("frq")),
                tags=tags,
            )
        )
    entries.sort(key=lambda e: e.word)
    return entries


def book_words(entries: Iterable[WordEntry], spec: BookSpec) -> List[WordEntry]:
    """The words of one book in study order.

    Words the learner should already know from an easier syllabus come last;
    within each group the most frequent words come first, and words without
    frequency data come last.
    """
    words = [e for e in entries if spec.tag in e.tags]
    if spec.limit is not None:
        words = [e for e in words if e.frq is not None]
    basics = set(spec.basics)
    words.sort(
        key=lambda e: (bool(basics & set(e.tags)), e.frq is None, e.frq or 0, e.word)
    )
    return words[: spec.limit] if spec.limit is not None else words


def select_words(
    rows: Iterable[dict], tag: str = "cet4", limit: int = 1000
) -> List[WordEntry]:
    """The `limit` most frequent words carrying `tag`, cleaned."""
    spec = BookSpec(name="", description="", tag=tag, limit=limit)
    candidates = []
    for row in rows:
        word = row["word"].strip()
        if not _is_plain_word(word) or tag not in row.get("tag", "").split():
            continue
        frq = _parse_frq(row.get("frq"))
        translation = clean_translation(row.get("translation", ""))
        if frq is None or not translation:
            continue
        candidates.append(
            WordEntry(word, normalize_phonetic(row.get("phonetic", "")), translation, frq, (tag,))
        )
    return book_words(candidates, spec)


def read_ecdict(path: str) -> Iterator[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


WORDLIST_FIELDS = ["word", "phonetic", "translation", "frq", "tags"]


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
                    "frq": e.frq or "",
                    "tags": " ".join(e.tags),
                }
            )


def read_wordlist(path: str) -> List[WordEntry]:
    with open(path, encoding="utf-8", newline="") as f:
        return [
            WordEntry(
                word=row["word"],
                phonetic=row["phonetic"] or None,
                translation=row["translation"],
                frq=_parse_frq(row.get("frq")),
                tags=tuple((row.get("tags") or "").split()),
            )
            for row in csv.DictReader(f)
        ]


def count_by_book(entries: Iterable[WordEntry]) -> Dict[str, int]:
    entries = list(entries)
    return {spec.name: len(book_words(entries, spec)) for spec in BOOKS}
