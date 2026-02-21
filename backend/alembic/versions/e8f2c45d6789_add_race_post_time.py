"""add race post_time

Revision ID: e8f2c45d6789
Revises: d7f1b34c5678
Create Date: 2026-02-21 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8f2c45d6789"
down_revision: Union[str, None] = "d7f1b34c5678"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("races", sa.Column("post_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("races", "post_time")
