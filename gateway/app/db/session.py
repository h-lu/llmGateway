from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gateway.app.core.config import settings


def get_engine(database_url: str | None = None):
    return create_engine(database_url or settings.database_url, future=True)


def get_session_maker(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
