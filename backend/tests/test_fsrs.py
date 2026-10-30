"""FSRS scheduler tests.

GOLDEN holds outputs recorded from the reference implementation py-fsrs 6.3.2
(fuzzing off, each answer given exactly when the card was due). Each row is
(rating, state, step, stability, difficulty, seconds until next review).
"""
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.srs import CardState, MemoryState, Rating, Scheduler

START = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)

GOLDEN = {
    'good_every_time': [
        (3, 'learning', 1, 2.306500, 2.118104, 600),
        (3, 'review', None, 2.306500, 2.111214, 172800),
        (3, 'review', None, 10.971048, 2.104331, 950400),
        (3, 'review', None, 46.316858, 2.097455, 3974400),
        (3, 'review', None, 162.999816, 2.090586, 14083200),
    ],
    'forget_then_recover': [
        (3, 'learning', 1, 2.306500, 2.118104, 600),
        (3, 'review', None, 2.306500, 2.111214, 172800),
        (3, 'review', None, 10.971048, 2.104331, 950400),
        (1, 'relearning', 0, 1.539013, 7.389976, 600),
        (3, 'review', None, 1.571842, 7.377814, 172800),
        (3, 'review', None, 4.934769, 7.365665, 432000),
    ],
    'easy_first': [
        (4, 'review', None, 8.295600, 1.000000, 691200),
        (4, 'review', None, 65.624226, 1.000000, 5702400),
        (4, 'review', None, 396.775023, 1.000000, 34300800),
    ],
    'hard_struggle': [
        (2, 'learning', 0, 1.293100, 5.112171, 330),
        (2, 'learning', 0, 1.293100, 6.740460, 330),
        (1, 'learning', 0, 0.451403, 8.913840, 60),
        (2, 'learning', 0, 0.451403, 9.264184, 330),
        (3, 'learning', 1, 0.499783, 9.250149, 600),
    ],
}


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_matches_reference_implementation(name):
    scheduler = Scheduler()
    card = MemoryState()
    now = START
    for rating, state, step, stability, difficulty, seconds in GOLDEN[name]:
        card = scheduler.review(card, Rating(rating), now)
        assert card.state.value == state
        assert card.step == step
        assert card.stability == pytest.approx(stability, abs=1e-6)
        assert card.difficulty == pytest.approx(difficulty, abs=1e-6)
        assert card.due - now == timedelta(seconds=seconds)
        now = card.due


def test_new_card_good_goes_to_ten_minute_step():
    card = Scheduler().review(MemoryState(), Rating.GOOD, START)
    assert card.state == CardState.learning
    assert card.due == START + timedelta(minutes=10)
    assert card.last_review == START


def test_easy_on_new_card_skips_learning_steps():
    card = Scheduler().review(MemoryState(), Rating.EASY, START)
    assert card.state == CardState.review
    assert card.due - START >= timedelta(days=1)


def test_forgetting_a_review_card_moves_it_to_relearning():
    s = Scheduler()
    card = s.review(MemoryState(), Rating.EASY, START)
    card = s.review(card, Rating.AGAIN, card.due)
    assert card.state == CardState.relearning
    assert card.step == 0


def test_intervals_grow_when_always_remembered():
    s = Scheduler()
    card = s.review(MemoryState(), Rating.EASY, START)
    intervals = []
    for _ in range(5):
        now = card.due
        card = s.review(card, Rating.GOOD, now)
        intervals.append(card.due - now)
    assert intervals == sorted(intervals)
    assert intervals[-1] > intervals[0]


def test_harder_ratings_never_schedule_later_than_easier_ones():
    s = Scheduler()
    card = s.review(MemoryState(), Rating.EASY, START)
    now = card.due
    dues = [s.review(card, r, now).due for r in Rating]
    assert dues == sorted(dues)


def test_difficulty_stays_between_1_and_10():
    s = Scheduler()
    card, now = MemoryState(), START
    for rating in [Rating.AGAIN] * 20 + [Rating.EASY] * 20:
        card = s.review(card, rating, now)
        assert 1.0 <= card.difficulty <= 10.0
        now = card.due


def test_retrievability_is_about_90_percent_when_due():
    s = Scheduler()
    card = s.review(MemoryState(), Rating.EASY, START)
    card = s.review(card, Rating.GOOD, card.due)
    assert s.retrievability(card, card.last_review) == pytest.approx(1.0)
    assert s.retrievability(card, card.due) == pytest.approx(0.9, abs=0.02)


def test_new_card_has_zero_retrievability():
    assert Scheduler().retrievability(MemoryState(), START) == 0.0


def test_review_does_not_modify_the_input_card():
    original = MemoryState()
    Scheduler().review(original, Rating.GOOD, START)
    assert original == MemoryState()


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        Scheduler().review(MemoryState(), Rating.GOOD, datetime(2026, 11, 1))


def test_fuzz_keeps_interval_close():
    s = Scheduler(fuzz=random.Random(0).random)
    plain = Scheduler()
    card = plain.review(MemoryState(), Rating.EASY, START)
    for _ in range(3):
        card = plain.review(card, Rating.GOOD, card.due)
    now = card.due
    expected = plain.review(card, Rating.GOOD, now).due - now
    fuzzed = s.review(card, Rating.GOOD, now).due - now
    assert abs(fuzzed - expected) <= expected * 0.1 + timedelta(days=1)
