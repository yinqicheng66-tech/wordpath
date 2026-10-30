"""Request and response bodies for the API."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import QuizType
from app.srs import CardState


class RegisterRequest(BaseModel):
    email: EmailStr
    # bcrypt only uses the first 72 bytes of a password
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    timezone: str
    created_at: datetime


# ----- word books -----


class BookOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    word_count: int
    learned: int  # words of this book the user has started
    active: bool  # the book new words currently come from


class EnrollRequest(BaseModel):
    daily_new_limit: int = Field(default=20, ge=1, le=200)


class EnrollmentOut(BaseModel):
    book_id: int
    daily_new_limit: int


# ----- study -----


class TodayOut(BaseModel):
    book_id: int
    daily_new_limit: int
    new_today: int
    new_remaining: int
    due_count: int


class OptionOut(BaseModel):
    word_id: int
    text: str


class QuestionOut(BaseModel):
    card_id: int
    quiz_type: QuizType
    is_new: bool
    prompt: str
    phonetic: Optional[str] = None
    audio_text: Optional[str] = None
    answer_length: Optional[int] = None
    options: List[OptionOut] = []


class NextOut(BaseModel):
    done: bool
    question: Optional[QuestionOut] = None


class AnswerRequest(BaseModel):
    card_id: int
    quiz_type: QuizType
    choice_word_id: Optional[int] = None  # meaning / listening
    spelling: Optional[str] = Field(default=None, max_length=64)  # spelling
    # Only used when the answer is right: 2 = hard, 3 = good, 4 = easy.
    rating: Optional[int] = Field(default=None, ge=2, le=4)
    response_ms: Optional[int] = Field(default=None, ge=0)


class AnswerOut(BaseModel):
    is_correct: bool
    rating: int
    word_id: int
    word: str
    translation: str
    state: CardState
    next_due_at: datetime


# ----- stats -----


class DayCountOut(BaseModel):
    date: date
    reviews: int


class StatsOut(BaseModel):
    streak_days: int
    learned_words: int
    mastered_words: int
    today_reviews: int
    today_correct: int
    daily: List[DayCountOut]
