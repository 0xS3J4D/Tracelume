from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from tracelume.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True)


def init_db() -> None:
    from tracelume import models  # noqa: F401  (register tables)

    s = get_settings()
    if s.database_url.startswith("sqlite:///"):
        from pathlib import Path

        Path(s.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
