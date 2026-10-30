import random
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_now, get_rng, get_scheduler
from app.db import get_db
from app.models import QuizType, User
from app.schemas import AnswerOut, AnswerRequest, NextOut, QuestionOut, TodayOut
from app.services import study
from app.srs import Scheduler

router = APIRouter(prefix="/study", tags=["study"])


def _no_book() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a word book first"
    )


@router.get("/today", response_model=TodayOut)
def today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now=Depends(get_now),
) -> TodayOut:
    try:
        return TodayOut(**asdict(study.today_summary(db, user, now)))
    except study.StudyError:
        raise _no_book()


@router.get("/next", response_model=NextOut)
def next_question(
    mode: QuizType = QuizType.meaning,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now=Depends(get_now),
    rng: random.Random = Depends(get_rng),
) -> NextOut:
    try:
        card = study.next_card(db, user, now)
    except study.StudyError:
        raise _no_book()
    if card is None:
        db.commit()
        return NextOut(done=True)
    question = study.build_question(db, user, card, mode, rng)
    db.commit()  # keeps a newly introduced card
    return NextOut(done=False, question=QuestionOut(**asdict(question)))


@router.post("/answer", response_model=AnswerOut)
def answer(
    body: AnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now=Depends(get_now),
    scheduler: Scheduler = Depends(get_scheduler),
) -> AnswerOut:
    try:
        result = study.submit_answer(
            db,
            user,
            card_id=body.card_id,
            quiz_type=body.quiz_type,
            choice_word_id=body.choice_word_id,
            spelling=body.spelling,
            self_rating=body.rating,
            response_ms=body.response_ms,
            now=now,
            scheduler=scheduler,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    db.commit()
    return AnswerOut(
        is_correct=result.is_correct,
        rating=int(result.rating),
        word=result.word,
        translation=result.translation,
        state=result.state,
        next_due_at=result.next_due_at,
    )
