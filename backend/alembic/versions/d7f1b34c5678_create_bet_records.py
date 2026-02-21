"""create bet_records table

Revision ID: d7f1b34c5678
Revises: c6e0a23b4567
Create Date: 2026-02-20 23:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7f1b34c5678"
down_revision: Union[str, None] = "c6e0a23b4567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bet_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "race_id",
            sa.Uuid(),
            sa.ForeignKey("races.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("bet_date", sa.Date(), nullable=False),
        sa.Column("bet_type", sa.String(16), nullable=False),
        sa.Column("horse_names", sa.Text(), nullable=False),
        sa.Column("amount_yen", sa.Integer(), nullable=False),
        sa.Column("odds_at_bet", sa.Numeric(8, 1), nullable=True),
        sa.Column("actual_payout", sa.Integer(), nullable=True),
        sa.Column("is_hit", sa.Boolean(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("bet_records")
