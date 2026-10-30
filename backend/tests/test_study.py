from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.importer import import_words
from app.models import Card, ReviewLog
from app.services.study import start_of_local_day
from app.srs import CardState
from app.wordbank import WordEntry

WORDS = [
    WordEntry("state", "steit", "n. 州，状态\na. 国家的", 1),
    WordEntry("might", "mait", "aux. 可能，也许", 2),
    WordEntry("part", "pɑ:t", "n. 部分，零件", 3),
    WordEntry("system", "'sistəm", "n. 系统，体系", 4),
    WordEntry("program", "'prəugræm", "n. 节目，程序", 5),
    WordEntry("element", "'elimənt", "n. 元素，要素", 6),
]


@pytest.fixture
def book_id(client):
    with client.SessionLocal() as db:
        book = import_words(db, WORDS)
        db.commit()
        return book.id


def login(client, email="a@example.com"):
    token = client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user(client, book_id):
    headers = login(client)
    r = client.post(
        f"/api/books/{book_id}/enroll", json={"daily_new_limit": 2}, headers=headers
    )
    assert r.status_code == 200
    return headers


def next_q(client, headers, mode="meaning"):
    r = client.get("/api/study/next", params={"mode": mode}, headers=headers)
    assert r.status_code == 200
    return r.json()


def correct_option(client, question):
    with client.SessionLocal() as db:
        return db.get(Card, question["card_id"]).word_id


def answer(client, headers, question, correct=True, rating=None):
    right = correct_option(client, question)
    choice = right if correct else next(
        o["word_id"] for o in question["options"] if o["word_id"] != right
    )
    body = {"card_id": question["card_id"], "quiz_type": question["quiz_type"],
            "choice_word_id": choice}
    if rating:
        body["rating"] = rating
    r = client.post("/api/study/answer", json=body, headers=headers)
    assert r.status_code == 200
    return r.json()


# ----- books -----


def test_list_books_counts_words(client, book_id):
    headers = login(client)
    books = client.get("/api/books", headers=headers).json()
    assert books == [
        {"id": book_id, "name": "核心 1000 词", "description": books[0]["description"],
         "word_count": 6}
    ]


def test_enroll_unknown_book_is_404(client):
    headers = login(client)
    r = client.post("/api/books/999/enroll", json={}, headers=headers)
    assert r.status_code == 404


def test_study_requires_a_book(client, book_id):
    headers = login(client)
    assert client.get("/api/study/today", headers=headers).status_code == 400
    assert client.get("/api/study/next", headers=headers).status_code == 400


def test_study_requires_login(client):
    assert client.get("/api/study/today").status_code == 401


# ----- today / next -----


def test_today_after_enrolling(client, user):
    today = client.get("/api/study/today", headers=user).json()
    assert today["daily_new_limit"] == 2
    assert today["new_today"] == 0
    assert today["new_remaining"] == 2
    assert today["due_count"] == 0


def test_first_question_is_first_word_in_book(client, user):
    data = next_q(client, user)
    q = data["question"]
    assert data["done"] is False
    assert q["is_new"] is True
    assert q["prompt"] == "state"
    assert q["phonetic"] == "steit"
    assert len(q["options"]) == 4
    texts = [o["text"] for o in q["options"]]
    assert "n. 州，状态" in texts  # only the first line of the translation
    assert len(set(texts)) == 4


def test_unanswered_card_is_shown_again(client, user):
    first = next_q(client, user)["question"]["card_id"]
    second = next_q(client, user)["question"]["card_id"]
    assert first == second


def test_listening_options_are_english_words(client, user):
    q = next_q(client, user, mode="listening")["question"]
    assert q["audio_text"] == "state"
    assert q["prompt"] == ""
    assert "state" in [o["text"] for o in q["options"]]


def test_spelling_question_hides_the_word(client, user):
    q = next_q(client, user, mode="spelling")["question"]
    assert q["prompt"] == "n. 州，状态\na. 国家的"
    assert q["answer_length"] == 5
    assert q["options"] == []
    assert "state" not in str(q)


# ----- answers -----


def test_correct_answer_moves_to_ten_minute_step(client, user, clock):
    q = next_q(client, user)["question"]
    result = answer(client, user, q)
    assert result["is_correct"] is True
    assert result["rating"] == 3
    assert result["state"] == "learning"
    assert result["word"] == "state"
    due = datetime.fromisoformat(result["next_due_at"].replace("Z", "+00:00"))
    assert (due - clock.now).total_seconds() == 600

    with client.SessionLocal() as db:
        card = db.get(Card, q["card_id"])
        assert card.reps == 1
        logs = db.scalars(select(ReviewLog).where(ReviewLog.card_id == card.id)).all()
        assert [(log.rating, log.is_correct) for log in logs] == [(3, True)]


def test_wrong_answer_counts_as_forgot(client, user):
    q = next_q(client, user)["question"]
    result = answer(client, user, q, correct=False, rating=4)
    assert result["is_correct"] is False
    assert result["rating"] == 1  # the self-rating is ignored when wrong


def test_easy_rating_skips_learning_steps(client, user):
    q = next_q(client, user)["question"]
    assert answer(client, user, q, rating=4)["state"] == "review"


@pytest.mark.parametrize(
    "typed, expected", [("state", True), ("  State ", True), ("stat", False), ("", False)]
)
def test_spelling_is_case_and_space_insensitive(client, user, typed, expected):
    q = next_q(client, user, mode="spelling")["question"]
    r = client.post(
        "/api/study/answer",
        json={"card_id": q["card_id"], "quiz_type": "spelling", "spelling": typed},
        headers=user,
    )
    assert r.json()["is_correct"] is expected


def test_rating_must_be_2_to_4(client, user):
    q = next_q(client, user)["question"]
    r = client.post(
        "/api/study/answer",
        json={"card_id": q["card_id"], "quiz_type": "meaning", "rating": 1},
        headers=user,
    )
    assert r.status_code == 422


def test_cannot_answer_another_users_card(client, user):
    q = next_q(client, user)["question"]
    other = login(client, email="b@example.com")
    r = client.post(
        "/api/study/answer",
        json={"card_id": q["card_id"], "quiz_type": "meaning", "choice_word_id": 1},
        headers=other,
    )
    assert r.status_code == 404


# ----- daily flow -----


def test_daily_new_word_limit_and_learning_steps(client, user, clock):
    # Learn the 2 new words allowed today.
    for expected in ["state", "might"]:
        q = next_q(client, user)["question"]
        assert q["prompt"] == expected
        answer(client, user, q)

    # Both are now waiting 10 minutes, and the new-word limit is used up.
    assert next_q(client, user) == {"done": True, "question": None}
    today = client.get("/api/study/today", headers=user).json()
    assert today["new_today"] == 2
    assert today["new_remaining"] == 0

    # 10 minutes later the first word comes back.
    clock.advance(minutes=10)
    q = next_q(client, user)["question"]
    assert q["prompt"] == "state"
    assert q["is_new"] is False


def test_new_words_unlock_the_next_local_day(client, user, clock):
    for _ in range(2):
        answer(client, user, next_q(client, user)["question"], rating=4)
    assert next_q(client, user)["done"] is True

    clock.advance(hours=12)  # 9pm the same day in Toronto: still today
    assert client.get("/api/study/today", headers=user).json()["new_remaining"] == 0
    clock.advance(hours=5)  # 2am the next day
    assert client.get("/api/study/today", headers=user).json()["new_remaining"] == 2


def test_forgetting_a_review_card_counts_a_lapse(client, user, clock):
    q = next_q(client, user)["question"]
    answer(client, user, q, rating=4)  # straight to review
    with client.SessionLocal() as db:
        due = db.get(Card, q["card_id"]).due_at
    clock.now = due.replace(tzinfo=timezone.utc)

    q2 = next_q(client, user)["question"]
    assert q2["card_id"] == q["card_id"]
    assert answer(client, user, q2, correct=False)["state"] == "relearning"
    with client.SessionLocal() as db:
        card = db.get(Card, q["card_id"])
        assert card.lapses == 1
        assert card.reps == 2
        assert card.state == CardState.relearning


def test_finishing_the_book(client, book_id, clock):
    headers = login(client)
    client.post(f"/api/books/{book_id}/enroll", json={"daily_new_limit": 50}, headers=headers)
    for _ in range(len(WORDS)):
        answer(client, headers, next_q(client, headers)["question"], rating=4)
    assert next_q(client, headers)["done"] is True


# ----- time zones -----


def test_start_of_local_day_uses_user_time_zone():
    # 01:00 UTC on Nov 3 is still Nov 2 in Toronto (UTC-5 after DST ends).
    now = datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc)
    start = start_of_local_day(now, "America/Toronto")
    assert start == datetime(2026, 11, 2, 5, 0, tzinfo=timezone.utc)


def test_unknown_time_zone_falls_back_to_utc():
    now = datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc)
    assert start_of_local_day(now, "Mars/Base") == datetime(2026, 11, 3, tzinfo=timezone.utc)
