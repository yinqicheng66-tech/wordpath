from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_now
from app.db import get_db
from app.models import BookWord, Card, User, WordBook
from app.schemas import BookOut, EnrollmentOut, EnrollRequest
from app.services import study
from app.srs import CardState

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=List[BookOut])
def list_books(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> List[BookOut]:
    rows = db.execute(
        select(WordBook, func.count(BookWord.word_id))
        .outerjoin(BookWord, BookWord.book_id == WordBook.id)
        .group_by(WordBook.id)
        .order_by(WordBook.id)
    ).all()
    learned = dict(
        db.execute(
            select(BookWord.book_id, func.count())
            .join(Card, Card.word_id == BookWord.word_id)
            .where(Card.user_id == user.id, Card.state != CardState.new)
            .group_by(BookWord.book_id)
        ).all()
    )
    active = study.active_enrollment(db, user)
    return [
        BookOut(
            id=b.id,
            name=b.name,
            description=b.description,
            word_count=n,
            learned=learned.get(b.id, 0),
            active=active is not None and active.book_id == b.id,
        )
        for b, n in rows
    ]


@router.post("/{book_id}/enroll", response_model=EnrollmentOut)
def enroll(
    book_id: int,
    body: EnrollRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now=Depends(get_now),
) -> EnrollmentOut:
    if db.get(WordBook, book_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    enrollment = study.enroll(db, user, book_id, body.daily_new_limit, now)
    db.commit()
    return EnrollmentOut(
        book_id=enrollment.book_id, daily_new_limit=enrollment.daily_new_limit
    )
