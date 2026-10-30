import ssl
from typing import Any, Dict, Iterator, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Hosting providers (Neon, Render, Heroku...) hand out URLs like
#   postgres://user:pass@host/db?sslmode=require
# We use the pure-Python pg8000 driver, which wants the scheme
# "postgresql+pg8000" and takes SSL as a Python ssl context instead of a
# query parameter.
_SSL_MODES_THAT_ENCRYPT = {"require", "verify-ca", "verify-full"}


def engine_args(url: str) -> Tuple[str, Dict[str, Any]]:
    """Return (SQLAlchemy URL, connect_args) for a database URL from any provider."""
    parts = urlsplit(url)
    if not parts.scheme.startswith("postgres"):
        return url, {}  # e.g. SQLite in tests
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+pg8000"

    connect_args: Dict[str, Any] = {}
    query = []
    for key, value in parse_qsl(parts.query):
        if key == "sslmode":
            if value in _SSL_MODES_THAT_ENCRYPT:
                connect_args["ssl_context"] = ssl.create_default_context()
        elif key == "channel_binding":
            continue  # libpq-only option; pg8000 negotiates this itself
        else:
            query.append((key, value))

    return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query))), connect_args


_url, _connect_args = engine_args(settings.database_url)
engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
