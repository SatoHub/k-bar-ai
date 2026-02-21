"""add scraping tables and columns

Revision ID: a3c8e5f01234
Revises: 84f2495ad016
Create Date: 2026-02-20 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c8e5f01234"
down_revision: Union[str, None] = "84f2495ad016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New tables ---

    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("race_id", sa.Uuid(), nullable=False),
        sa.Column("post_position", sa.SmallInteger(), nullable=False),
        sa.Column("win_odds", sa.Numeric(precision=8, scale=1), nullable=True),
        sa.Column("win_favorite", sa.SmallInteger(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["race_id"],
            ["races.id"],
            name=op.f("fk_odds_snapshots_race_id_races"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_odds_snapshots")),
    )
    op.create_index(
        op.f("ix_odds_snapshots_race_id"),
        "odds_snapshots",
        ["race_id"],
    )
    op.create_index(
        "ix_odds_snapshots_race_post",
        "odds_snapshots",
        ["race_id", "post_position"],
    )

    op.create_table(
        "scrape_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=16), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("target_race_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("records_affected", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scrape_logs")),
    )

    # --- Add columns to existing tables ---

    op.add_column(
        "races", sa.Column("data_source", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "race_entries", sa.Column("data_source", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "horses",
        sa.Column("netkeiba_id", sa.String(length=20), nullable=True),
    )
    op.create_index(
        op.f("uq_horses_netkeiba_id"),
        "horses",
        ["netkeiba_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("uq_horses_netkeiba_id"), table_name="horses")
    op.drop_column("horses", "netkeiba_id")
    op.drop_column("race_entries", "data_source")
    op.drop_column("races", "data_source")
    op.drop_table("scrape_logs")
    op.drop_index("ix_odds_snapshots_race_post", table_name="odds_snapshots")
    op.drop_index(op.f("ix_odds_snapshots_race_id"), table_name="odds_snapshots")
    op.drop_table("odds_snapshots")
