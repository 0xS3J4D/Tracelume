"""jobs may exist before their evidence (acquisition)

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("job") as b:
        b.alter_column("evidence_id", existing_type=sa.VARCHAR(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("job") as b:
        b.alter_column("evidence_id", existing_type=sa.VARCHAR(), nullable=False)
