from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, event
from sqlmodel import Session, create_engine

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


MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    return cfg


def init_db() -> None:
    """Bring the schema to the latest version (safe to run on every start)."""
    from tracelume import models  # noqa: F401  (register tables)

    s = get_settings()
    if s.database_url.startswith("sqlite:///"):
        Path(s.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql(
                "SELECT pg_advisory_xact_lock(4711)"
            )  # api + worker start together
        cfg = alembic_config()
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
