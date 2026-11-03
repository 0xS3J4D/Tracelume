from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from tracelume.db import get_engine


def test_models_and_migrations_are_in_sync(client: TestClient) -> None:
    """If this fails: generate a new migration (see CONTRIBUTING.md)."""
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == []
