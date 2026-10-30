from datetime import date, timedelta

import pytest

from app.importer import import_words
from app.services.stats import streak
from app.wordbank import WordEntry

WORDS = [WordEntry(w, None, f"n. 词{i}", i) for i, w in enumerate(
    ["alpha", "bravo", "charlie", "delta", "echo"], start=1)]


@pytest.fixture
def user(client):
    with client.SessionLocal() as db:
        book_id = import_words(db, WORDS).id
        db.commit()
    token = client.post(
        "/api/auth/register", json={"email": "s@example.com", "password": "password123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post(f"/api/books/{book_id}/enroll", json={"daily_new_limit": 3}, headers=headers)
    return headers


def study_one(client, headers, correct=True):
    q = client.get("/api/study/next", headers=headers).json()["question"]
    options = [o["word_id"] for o in q["options"]]
    first = client.post("/api/study/answer", headers=headers, json={
        "card_id": q["card_id"], "quiz_type": "meaning", "choice_word_id": options[0]})
    return first.json()


def stats(client, headers):
    return client.get("/api/stats/summary", headers=headers).json()


def test_empty_stats(client, user):
    s = stats(client, user)
    assert s["streak_days"] == 0
    assert s["learned_words"] == 0
    assert s["today_reviews"] == 0
    assert len(s["daily"]) == 14
    assert s["daily"][-1] == {"date": "2026-11-02", "reviews": 0}


def test_stats_count_today(client, user):
    results = [study_one(client, user) for _ in range(3)]
    s = stats(client, user)
    assert s["today_reviews"] == 3
    assert s["today_correct"] == sum(r["is_correct"] for r in results)
    assert s["learned_words"] == 3
    assert s["streak_days"] == 1
    assert s["daily"][-1]["reviews"] == 3


def test_streak_survives_until_end_of_next_day(client, user, clock):
    study_one(client, user)
    clock.advance(days=1)
    assert stats(client, user)["streak_days"] == 1  # nothing yet today, still alive
    clock.advance(days=1)
    assert stats(client, user)["streak_days"] == 0  # a whole day was missed


def test_streak_counts_consecutive_days():
    today = date(2026, 11, 10)
    days = {today - timedelta(days=i) for i in (0, 1, 2, 4)}
    assert streak(days, today) == 3
    assert streak(days - {today}, today) == 2  # counts back from yesterday
    assert streak(set(), today) == 0


def test_stats_require_login(client):
    assert client.get("/api/stats/summary").status_code == 401
