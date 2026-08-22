"""fix race_entry unique index: (race_id, post_position) -> (race_id, horse_id)

The old index used (race_id, post_position), which fails when post_position
is NULL because SQL NULL != NULL, creating duplicate entries.
This migration cleans up existing duplicates and switches to (race_id, horse_id).

Revision ID: d4e5f6a7b890
Revises: c3d4e5f6a789
Create Date: 2026-02-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b890"
down_revision: Union[str, None] = "c3d4e5f6a789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Remove duplicate race_entries, keeping the one with most data
    #    (prefer rows with post_position set, then the most recently created)
    op.execute("""
        DELETE FROM race_entries
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY race_id, horse_id
                           ORDER BY
                               CASE WHEN post_position IS NOT NULL THEN 0 ELSE 1 END,
                               id
                       ) AS rn
                FROM race_entries
            ) ranked
            WHERE rn > 1
        )
    """)

    # 2. Drop old unique index
    op.drop_index("ix_race_entries_race_post", table_name="race_entries")

    # 3. Create new unique index on (race_id, horse_id)
    op.create_index(
        "ix_race_entries_race_horse",
        "race_entries",
        ["race_id", "horse_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_race_entries_race_horse", table_name="race_entries")
    op.create_index(
        "ix_race_entries_race_post",
        "race_entries",
        ["race_id", "post_position"],
        unique=True,
    )
