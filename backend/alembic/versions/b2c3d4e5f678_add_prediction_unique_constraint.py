"""add prediction_logs unique constraint

Revision ID: b2c3d4e5f678
Revises: a1b2c3d4e567
Create Date: 2026-02-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f678"
down_revision: Union[str, None] = "a1b2c3d4e567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 既存の重複データを削除（各 (race_id, horse_id, model_version_id) で最新1件だけ残す）
    op.execute(
        """
        DELETE FROM prediction_logs
        WHERE id NOT IN (
            SELECT DISTINCT ON (race_id, horse_id, model_version_id) id
            FROM prediction_logs
            ORDER BY race_id, horse_id, model_version_id, created_at DESC
        )
        """
    )

    # 2. ユニーク制約を追加
    op.create_unique_constraint(
        "uq_prediction_logs_race_horse_model",
        "prediction_logs",
        ["race_id", "horse_id", "model_version_id"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_prediction_logs_race_horse_model",
        "prediction_logs",
        type_="unique",
    )
