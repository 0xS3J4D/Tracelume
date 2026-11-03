from alembic import context
from sqlmodel import SQLModel

from tracelume import models  # noqa: F401  (register tables)
from tracelume.db import get_engine

target_metadata = SQLModel.metadata


def run() -> None:
    connectable = context.config.attributes.get("connection") or get_engine().connect()
    context.configure(
        connection=connectable,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run()
