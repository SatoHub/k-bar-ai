"""add miss_reason_logs and improvement_proposals tables

Revision ID: c3d4e5f6a789
Revises: b2c3d4e5f678
Create Date: 2026-02-22 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a789"
down_revision: Union[str, None] = "b2c3d4e5f678"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "miss_reason_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("race_id", sa.Uuid(), nullable=False),
        sa.Column("bet_type", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_miss_reason_logs")),
        sa.ForeignKeyConstraint(
            ["race_id"],
            ["races.id"],
            name=op.f("fk_miss_reason_logs_race_id_races"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_miss_reason_logs_race_id"),
        "miss_reason_logs",
        ["race_id"],
    )

    op.create_table(
        "improvement_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("proposal_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("user_response_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_improvement_proposals")),
    )
    op.create_index(
        op.f("ix_improvement_proposals_month"),
        "improvement_proposals",
        ["month"],
    )
    op.create_index(
        op.f("ix_improvement_proposals_status"),
        "improvement_proposals",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_improvement_proposals_status"),
        table_name="improvement_proposals",
    )
    op.drop_index(
        op.f("ix_improvement_proposals_month"),
        table_name="improvement_proposals",
    )
    op.drop_table("improvement_proposals")
    op.drop_index(
        op.f("ix_miss_reason_logs_race_id"),
        table_name="miss_reason_logs",
    )
    op.drop_table("miss_reason_logs")
