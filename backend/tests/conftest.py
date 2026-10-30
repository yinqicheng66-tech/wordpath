"""Shared test fixtures: an API client backed by an in-memory SQLite database."""
import random
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.api.deps import get_now, get_rng, get_scheduler
from app.db import Base, get_db
from app.main import app
from app.srs import Scheduler


class Clock:
    """A clock the tests can move forward."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc)  # 9:00 in Toronto

    def advance(self, **kwargs) -> None:
        from datetime import timedelta

        self.now += timedelta(**kwargs)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory database for the whole test
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_now] = lambda: clock.now
    app.dependency_overrides[get_rng] = lambda: random.Random(0)
    app.dependency_overrides[get_scheduler] = lambda: Scheduler()  # no fuzz
    with TestClient(app) as c:
        c.SessionLocal = TestingSession  # lets tests look inside the database
        yield c
    app.dependency_overrides.clear()
