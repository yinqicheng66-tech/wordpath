from pathlib import Path

from app.wordbank import (
    BOOKS,
    WordEntry,
    book_words,
    clean_translation,
    extract_entries,
    normalize_phonetic,
    read_wordlist,
    select_words,
    write_wordlist,
)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "words.csv"


def row(word, tag="cet4", frq="100", translation="n. 苹果", phonetic="'æpl"):
    return {
        "word": word,
        "tag": tag,
        "frq": frq,
        "translation": translation,
        "phonetic": phonetic,
    }


def test_clean_translation_drops_domain_lines_and_limits_meanings():
    raw = "n. 州, 状态, 情形, 国家, 政府\\na. 国家的\\n[计] 状态"
    assert clean_translation(raw) == "n. 州，状态，情形，国家\na. 国家的"


def test_clean_translation_keeps_at_most_three_parts_of_speech():
    raw = "n. 一\\nvt. 二\\nvi. 三\\nadv. 四"
    assert clean_translation(raw).count("\n") == 2


def test_clean_translation_handles_lines_without_part_of_speech():
    assert clean_translation("苹果；苹果树") == "苹果，苹果树"


def test_clean_translation_returns_empty_when_only_domain_lines():
    assert clean_translation("[网络] 胡德\\n[医] 罩") == ""


def test_normalize_phonetic_fixes_cyrillic_schwa():
    assert normalize_phonetic("ә'geinst") == "ə'geinst"


def test_normalize_phonetic_empty_is_none():
    assert normalize_phonetic("  ") is None


def test_select_words_filters_and_sorts_by_frequency():
    rows = [
        row("banana", frq="300"),
        row("apple", frq="100"),
        row("cherry", frq="200"),
        row("ice cream", frq="50"),  # phrase
        row("Paris", frq="60"),  # proper noun
        row("rare", frq="0"),  # no frequency data
        row("thesis", tag="gre", frq="70"),  # not CET-4
        row("domain", frq="80", translation="[计] 域"),  # nothing left after cleaning
    ]
    assert [e.word for e in select_words(rows)] == ["apple", "cherry", "banana"]


def test_select_words_respects_limit():
    rows = [row(w, frq=str(i)) for i, w in enumerate(["aa", "bb", "cc"], start=1)]
    assert [e.word for e in select_words(rows, limit=2)] == ["aa", "bb"]


def test_clean_translation_strips_carriage_returns_and_inline_labels():
    raw = "第一的\\r\\nn. 优势, [经] 利益\r\\nart. [计] 累加器"
    assert clean_translation(raw) == "第一的\nn. 优势，利益"


def test_extract_entries_keeps_only_exam_tags():
    rows = [
        row("apple", tag="zk gk cet4"),
        row("banana", tag="unknown"),  # not an exam we know
        row("cherry", tag="gre", frq="0"),  # kept even without frequency data
    ]
    entries = extract_entries(rows)
    assert [(e.word, e.tags, e.frq) for e in entries] == [
        ("apple", ("cet4", "gk", "zk"), 100),
        ("cherry", ("gre",), None),
    ]


def test_book_words_puts_unknown_frequency_last_and_applies_limit():
    entries = [
        WordEntry("rare", None, "x", None, ("cet4",)),
        WordEntry("common", None, "x", 5, ("cet4",)),
        WordEntry("other", None, "x", 1, ("gre",)),
    ]
    full = next(b for b in BOOKS if b.tag == "cet4" and b.limit is None)
    starter = next(b for b in BOOKS if b.limit is not None)
    assert [e.word for e in book_words(entries, full)] == ["common", "rare"]
    assert [e.word for e in book_words(entries, starter)] == ["common"]


def test_wordlist_round_trip(tmp_path):
    entries = [
        WordEntry("state", "steit", "n. 州，状态\na. 国家的", 137, ("cet4", "gk")),
        WordEntry("ubiquitous", None, "a. 无所不在的", None, ("gre",)),
    ]
    path = tmp_path / "words.csv"
    write_wordlist(entries, str(path))
    assert read_wordlist(str(path)) == entries


def test_bundled_word_books():
    entries = read_wordlist(str(DATA_FILE))
    assert len({e.word for e in entries}) == len(entries) > 14000
    assert all(e.translation for e in entries)
    sizes = {spec.name: len(book_words(entries, spec)) for spec in BOOKS}
    assert sizes["四级高频 1000"] == 1000
    assert all(n > 1000 for name, n in sizes.items() if name != "四级高频 1000")


def test_advanced_books_put_basic_words_last():
    entries = [
        WordEntry("want", None, "x", 50, ("cet4", "gre", "zk")),  # very common, but basic
        WordEntry("regime", None, "x", 3000, ("cet6", "gre")),
        WordEntry("cite", None, "x", 4000, ("gre",)),
    ]
    gre = next(b for b in BOOKS if b.tag == "gre")
    assert [e.word for e in book_words(entries, gre)] == ["regime", "cite", "want"]
