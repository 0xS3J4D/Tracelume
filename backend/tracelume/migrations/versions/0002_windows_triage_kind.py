"""add windows_triage evidence kind

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

KINDS = (
    "disk_image",
    "android_fs",
    "ios_backup",
    "ios_fs",
    "memory_image",
    "windows_triage",
    "logs",
    "other",
)

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # allowed inside a transaction since PostgreSQL 12 (value not used in this migration)
        op.execute("ALTER TYPE evidencekind ADD VALUE IF NOT EXISTS 'windows_triage'")
    else:  # non-native enum: widen the VARCHAR
        with op.batch_alter_table("evidence") as b:
            b.alter_column(
                "kind",
                existing_type=sa.VARCHAR(12),
                type_=sa.Enum(*KINDS, name="evidencekind"),
                existing_nullable=False,
            )


def downgrade() -> None:
    pass  # enum values cannot be dropped safely in PostgreSQL
