"""add horse image_url

Revision ID: b5d9f12e6789
Revises: a3c8e5f01234
Create Date: 2026-02-20 23:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5d9f12e6789"
down_revision: Union[str, None] = "a3c8e5f01234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("horses", sa.Column("image_url", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("horses", "image_url")
