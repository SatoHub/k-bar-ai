"""create confirmed_win_odds & confirmed_payouts (self-contained JV-Data, synced)

JV-Data confirmed win odds (NL_O1 datakubun=5) and payouts (NL_HR) are pure
race-level data keyed by netkeiba race_id — they do NOT depend on the app's
races table. Materialize them into self-contained tables in the app DB,
populated on the home PC from the jravan FDW views and synced to VPS as data.
Production races (which DO overlap JV-Data dates) then join by race_id, and #3
model retraining reuses the same tables as features / ground truth.

Revision ID: f6a7b8c9d012
Revises: e5f6a7b8c901
Create Date: 2026-06-12 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d012"
down_revision: Union[str, None] = "e5f6a7b8c901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Confirmed win odds: one row per (race, horse-number).
    op.create_table(
        "confirmed_win_odds",
        sa.Column("race_id", sa.String(length=20), nullable=False),
        sa.Column("umaban", sa.SmallInteger(), nullable=False),
        sa.Column("win_odds", sa.Float(), nullable=True),
        sa.Column("win_favorite", sa.SmallInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("race_id", "umaban"),
    )

    # Confirmed payouts: one row per race (mirrors jravan.v_confirmed_payouts).
    op.create_table(
        "confirmed_payouts",
        sa.Column("race_id", sa.String(length=20), primary_key=True),
        sa.Column("runners", sa.Integer(), nullable=True),
        sa.Column("tan_umaban", sa.Text(), nullable=True),
        sa.Column("tan_pay", sa.BigInteger(), nullable=True),
        sa.Column("tan_ninki", sa.Integer(), nullable=True),
        sa.Column("fuku_umaban", sa.Text(), nullable=True),
        sa.Column("fuku_pay", sa.BigInteger(), nullable=True),
        sa.Column("fuku_ninki", sa.Integer(), nullable=True),
        sa.Column("umaren_kumi", sa.Text(), nullable=True),
        sa.Column("umaren_pay", sa.BigInteger(), nullable=True),
        sa.Column("wide_kumi", sa.Text(), nullable=True),
        sa.Column("wide_pay", sa.BigInteger(), nullable=True),
        sa.Column("umatan_kumi", sa.Text(), nullable=True),
        sa.Column("umatan_pay", sa.BigInteger(), nullable=True),
        sa.Column("sanrenfuku_kumi", sa.Text(), nullable=True),
        sa.Column("sanrenfuku_pay", sa.BigInteger(), nullable=True),
        sa.Column("sanrentan_kumi", sa.Text(), nullable=True),
        sa.Column("sanrentan_pay", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("confirmed_payouts")
    op.drop_table("confirmed_win_odds")
