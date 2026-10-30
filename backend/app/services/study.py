"""Study session logic: what to show next, building questions, grading answers.

The API layer (app/api/study.py) is a thin wrapper around these functions.
Time, randomness and the scheduler are passed in so tests can control them.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import BookWord, Card, QuizType, ReviewLog, User, UserBook, Word
from app.srs import CardState, MemoryState, Rating, Scheduler

NUM_OPTIONS = 4


class StudyError(Exception):
    """A request that cannot be served, e.g. the user has no word book yet."""


# ----- time helpers -----


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Databases may return naive datetimes (SQLite); we always store UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def start_of_local_day(now: datetime, tz_name: str) -> datetime:
    """Midnight of `now`'s date in the user's time zone, expressed in UTC."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    local = now.astimezone(tz)
    return datetime.combine(local.date(), time.min, tzinfo=tz).astimezone(timezone.utc)


# ----- word books -----


def active_enrollment(db: Session, user: User) -> Optional[UserBook]:
    """The word book the user picked most recently."""
    return db.scalar(
        select(UserBook)
        .where(UserBook.user_id == user.id)
        .order_by(UserBook.started_at.desc())
        .limit(1)
    )


def enroll(
    db: Session, user: User, book_id: int, daily_new_limit: int, now: datetime
) -> UserBook:
    enrollment = db.get(UserBook, (user.id, book_id))
    if enrollment is None:
        enrollment = UserBook(user_id=user.id, book_id=book_id)
        db.add(enrollment)
    enrollment.daily_new_limit = daily_new_limit
    enrollment.started_at = now  # makes it the active book
    db.flush()
    return enrollment


# ----- today's numbers -----


@dataclass
class TodaySummary:
    book_id: int
    daily_new_limit: int
    new_today: int
    new_remaining: int
    due_count: int


def today_summary(db: Session, user: User, now: datetime) -> TodaySummary:
    enrollment = active_enrollment(db, user)
    if enrollment is None:
        raise StudyError("Choose a word book first")
    day_start = start_of_local_day(now, user.timezone)
    new_today = db.scalar(
        select(func.count())
        .select_from(Card)
        .where(Card.user_id == user.id, Card.created_at >= day_start)
    )
    due_count = db.scalar(
        select(func.count())
        .select_from(Card)
        .where(Card.user_id == user.id, Card.due_at <= now)
    )
    return TodaySummary(
        book_id=enrollment.book_id,
        daily_new_limit=enrollment.daily_new_limit,
        new_today=new_today,
        new_remaining=max(0, enrollment.daily_new_limit - new_today),
        due_count=due_count,
    )


# ----- choosing the next card -----


def next_card(db: Session, user: User, now: datetime) -> Optional[Card]:
    """Due cards first (oldest due first), then a new word if today's limit allows."""
    due = db.scalar(
        select(Card)
        .where(Card.user_id == user.id, Card.due_at <= now)
        .order_by(Card.due_at, Card.id)
        .limit(1)
    )
    if due is not None:
        return due

    summary = today_summary(db, user, now)
    if summary.new_remaining == 0:
        return None

    already_seen = select(Card.word_id).where(Card.user_id == user.id)
    word_id = db.scalar(
        select(BookWord.word_id)
        .where(
            BookWord.book_id == summary.book_id,
            BookWord.word_id.not_in(already_seen),
        )
        .order_by(BookWord.position)
        .limit(1)
    )
    if word_id is None:
        return None  # finished the whole book

    card = Card(
        user_id=user.id,
        word_id=word_id,
        state=CardState.new,
        step=0,
        due_at=now,
        created_at=now,
    )
    db.add(card)
    db.flush()
    return card


# ----- questions -----


@dataclass
class Option:
    word_id: int
    text: str


@dataclass
class Question:
    card_id: int
    quiz_type: QuizType
    is_new: bool
    prompt: str
    phonetic: Optional[str] = None
    audio_text: Optional[str] = None
    answer_length: Optional[int] = None
    options: List[Option] = field(default_factory=list)


def first_line(translation: str) -> str:
    return translation.split("\n", 1)[0]


def _distractors(
    db: Session, book_id: int, word: Word, rng: random.Random
) -> List[Word]:
    candidates = list(
        db.scalars(
            select(Word)
            .join(BookWord, BookWord.word_id == Word.id)
            .where(BookWord.book_id == book_id, Word.id != word.id)
        )
    )
    # Avoid two options that would look the same.
    seen = {first_line(word.translation)}
    unique = []
    for c in candidates:
        key = first_line(c.translation)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return rng.sample(unique, min(NUM_OPTIONS - 1, len(unique)))


def build_question(
    db: Session, user: User, card: Card, quiz_type: QuizType, rng: random.Random
) -> Question:
    word = db.get(Word, card.word_id)
    is_new = card.state == CardState.new

    if quiz_type == QuizType.spelling:
        return Question(
            card_id=card.id,
            quiz_type=quiz_type,
            is_new=is_new,
            prompt=word.translation,
            answer_length=len(word.word),
        )

    enrollment = active_enrollment(db, user)
    book_id = enrollment.book_id if enrollment else None
    others = _distractors(db, book_id, word, rng) if book_id is not None else []
    choices = [word] + others
    rng.shuffle(choices)

    if quiz_type == QuizType.meaning:
        return Question(
            card_id=card.id,
            quiz_type=quiz_type,
            is_new=is_new,
            prompt=word.word,
            phonetic=word.phonetic,
            audio_text=word.word,
            options=[Option(w.id, first_line(w.translation)) for w in choices],
        )

    # listening: the browser speaks audio_text, the user picks the word
    return Question(
        card_id=card.id,
        quiz_type=quiz_type,
        is_new=is_new,
        prompt="",
        audio_text=word.word,
        options=[Option(w.id, w.word) for w in choices],
    )


# ----- answers -----


def normalize_spelling(text: str) -> str:
    return " ".join(text.strip().lower().split())


def is_correct_answer(
    word: Word,
    quiz_type: QuizType,
    choice_word_id: Optional[int],
    spelling: Optional[str],
) -> bool:
    if quiz_type == QuizType.spelling:
        return spelling is not None and normalize_spelling(spelling) == word.word.lower()
    return choice_word_id == word.id


def _to_memory(card: Card) -> MemoryState:
    return MemoryState(
        state=card.state,
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        due=as_utc(card.due_at),
        last_review=as_utc(card.last_review_at),
    )


@dataclass
class AnswerResult:
    is_correct: bool
    rating: Rating
    word: str
    translation: str
    state: CardState
    next_due_at: datetime


def submit_answer(
    db: Session,
    user: User,
    card_id: int,
    quiz_type: QuizType,
    choice_word_id: Optional[int],
    spelling: Optional[str],
    self_rating: Optional[int],
    response_ms: Optional[int],
    now: datetime,
    scheduler: Scheduler,
) -> AnswerResult:
    card = db.get(Card, card_id)
    if card is None or card.user_id != user.id:
        raise LookupError("Card not found")
    word = db.get(Word, card.word_id)

    correct = is_correct_answer(word, quiz_type, choice_word_id, spelling)
    # A wrong answer always counts as "forgot". A right answer uses the
    # user's own rating (hard / good / easy), defaulting to good.
    rating = Rating(self_rating) if correct and self_rating else Rating.GOOD
    if not correct:
        rating = Rating.AGAIN

    was_review = card.state == CardState.review
    memory = scheduler.review(_to_memory(card), rating, now)

    card.state = memory.state
    card.step = memory.step
    card.stability = memory.stability
    card.difficulty = memory.difficulty
    card.due_at = memory.due
    card.last_review_at = memory.last_review
    card.reps = (card.reps or 0) + 1
    if was_review and rating == Rating.AGAIN:
        card.lapses = (card.lapses or 0) + 1

    db.add(
        ReviewLog(
            card_id=card.id,
            quiz_type=quiz_type,
            rating=int(rating),
            is_correct=correct,
            response_ms=response_ms,
            reviewed_at=now,
        )
    )
    db.flush()
    return AnswerResult(
        is_correct=correct,
        rating=rating,
        word=word.word,
        translation=word.translation,
        state=memory.state,
        next_due_at=memory.due,
    )
