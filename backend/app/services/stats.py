"""Learning statistics shown on the home page."""
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import Card, ReviewLog, User
from app.services.study import as_utc, start_of_local_day
from app.srs import CardState

MASTERED_STABILITY_DAYS = 21  # remembered for 3+ weeks counts as mastered
HISTORY_DAYS = 14
STREAK_LOOKBACK_DAYS = 400


@dataclass
class DayCount:
    date: date
    reviews: int


@dataclass
class Summary:
    streak_days: int
    learned_words: int
    mastered_words: int
    today_reviews: int
    today_correct: int
    daily: List[DayCount]


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def streak(active_days: set, today: date) -> int:
    """Consecutive days with at least one review, ending today.

    If nothing has been reviewed yet today, the streak still counts up to
    yesterday, so it doesn't look broken first thing in the morning.
    """
    day = today if today in active_days else today - timedelta(days=1)
    count = 0
    while day in active_days:
        count += 1
        day -= timedelta(days=1)
    return count


def summary(db: Session, user: User, now: datetime) -> Summary:
    tz = _zone(user.timezone)
    today = now.astimezone(tz).date()
    since = start_of_local_day(now, user.timezone) - timedelta(days=STREAK_LOOKBACK_DAYS)

    rows = db.execute(
        select(ReviewLog.reviewed_at, ReviewLog.is_correct)
        .join(Card, Card.id == ReviewLog.card_id)
        .where(Card.user_id == user.id, ReviewLog.reviewed_at >= since)
    ).all()

    per_day: Counter = Counter()
    today_correct = 0
    for reviewed_at, is_correct in rows:
        day = as_utc(reviewed_at).astimezone(tz).date()
        per_day[day] += 1
        if day == today and is_correct:
            today_correct += 1

    learned = db.scalar(
        select(func.count())
        .select_from(Card)
        .where(Card.user_id == user.id, Card.state != CardState.new)
    )
    mastered = db.scalar(
        select(func.count())
        .select_from(Card)
        .where(
            Card.user_id == user.id,
            Card.state == CardState.review,
            Card.stability >= MASTERED_STABILITY_DAYS,
        )
    )
    daily = [
        DayCount(date=d, reviews=per_day.get(d, 0))
        for d in (today - timedelta(days=i) for i in range(HISTORY_DAYS - 1, -1, -1))
    ]
    return Summary(
        streak_days=streak(set(per_day), today),
        learned_words=learned,
        mastered_words=mastered,
        today_reviews=per_day.get(today, 0),
        today_correct=today_correct,
        daily=daily,
    )


