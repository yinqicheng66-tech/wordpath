from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.schemas import UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> User:
    return user
