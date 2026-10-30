from pathlib import Path

from app.wordbank import (
    WordEntry,
    clean_translation,
    normalize_phonetic,
    read_wordlist,
    select_words,
    write_wordlist,
)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "core_1000.csv"


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


def test_wordlist_round_trip(tmp_path):
    entries = [WordEntry("state", "steit", "n. 州，状态\na. 国家的", 137)]
    path = tmp_path / "words.csv"
    write_wordlist(entries, str(path))
    assert read_wordlist(str(path)) == entries


def test_bundled_wordlist_has_1000_unique_words():
    entries = read_wordlist(str(DATA_FILE))
    assert len(entries) == 1000
    assert len({e.word for e in entries}) == 1000
    assert all(e.translation for e in entries)
