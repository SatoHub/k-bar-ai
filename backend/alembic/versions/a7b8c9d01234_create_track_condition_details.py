"""create track_condition_details (JRA官製 含水率・クッション値)

JV-Data lacks 含水率 / クッション値 (only a coarse 良/稍重/重/不良 code). These
are scraped from the JRA official site per venue on race days and stored here,
joined to races by (racecourse_name, race_date).

Revision ID: a7b8c9d01234
Revises: f6a7b8c9d012
Create Date: 2026-06-13 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d01234"
down_revision: Union[str, None] = "f6a7b8c9d012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "track_condition_details",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("racecourse_name", sa.String(length=32), nullable=False),
        sa.Column("measured_date", sa.Date(), nullable=False),
        sa.Column("cushion_value", sa.Float(), nullable=True),
        sa.Column("turf_moisture_goal", sa.Float(), nullable=True),
        sa.Column("turf_moisture_4c", sa.Float(), nullable=True),
        sa.Column("dirt_moisture_goal", sa.Float(), nullable=True),
        sa.Column("dirt_moisture_4c", sa.Float(), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "racecourse_name", "measured_date", name="uq_track_cond_course_date"
        ),
    )
    op.create_index(
        "ix_track_condition_details_racecourse_name",
        "track_condition_details",
        ["racecourse_name"],
    )
    op.create_index(
        "ix_track_condition_details_measured_date",
        "track_condition_details",
        ["measured_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_track_condition_details_measured_date",
        table_name="track_condition_details",
    )
    op.drop_index(
        "ix_track_condition_details_racecourse_name",
        table_name="track_condition_details",
    )
    op.drop_table("track_condition_details")
