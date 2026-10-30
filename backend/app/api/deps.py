"""Shared FastAPI dependencies."""
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_access_token
from app.srs import Scheduler

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the logged-in user, or answer 401 if the token is missing or invalid."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def get_now() -> datetime:
    """Current time in UTC. Tests override this to control the clock."""
    return datetime.now(timezone.utc)


def get_rng() -> random.Random:
    return random.Random()


def get_scheduler() -> Scheduler:
    # Fuzzing spreads reviews out so words learned together don't all come due on the same day.
    return Scheduler(fuzz=random.random)
