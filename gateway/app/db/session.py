from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gateway.app.core.config import settings

_engine = None
_SessionLocal = None


def get_engine(database_url: str | None = None):
    global _engine
    if _engine is None:
        _engine = create_engine(database_url or settings.database_url, future=True)
    return _engine


def get_session_maker(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session():
    """Context manager for database sessions."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False
        )
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
