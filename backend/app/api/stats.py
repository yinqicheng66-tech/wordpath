from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_now
from app.db import get_db
from app.models import User
from app.schemas import StatsOut
from app.services import stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", response_model=StatsOut)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now=Depends(get_now),
) -> StatsOut:
    return StatsOut(**asdict(stats.summary(db, user, now)))
