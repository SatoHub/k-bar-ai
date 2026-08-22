"""add race head_count and stub_only

Revision ID: f9a3b56c7890
Revises: e8f2c45d6789
Create Date: 2026-02-21 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9a3b56c7890"
down_revision: Union[str, None] = "e8f2c45d6789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("races", sa.Column("head_count", sa.SmallInteger(), nullable=True))
    op.add_column(
        "races",
        sa.Column(
            "stub_only", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    op.drop_column("races", "stub_only")
    op.drop_column("races", "head_count")
