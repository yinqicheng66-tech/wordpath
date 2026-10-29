from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check used by deploys and CI."""
    return {"status": "ok"}
