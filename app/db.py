from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import database_url


class Base(DeclarativeBase):
    pass


def now():
    return datetime.now(UTC)


@lru_cache(maxsize=4)
def engine_for(url: str):
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    return engine


@contextmanager
def transaction():
    with Session(engine_for(database_url()), expire_on_commit=False) as session, session.begin():
        yield session
