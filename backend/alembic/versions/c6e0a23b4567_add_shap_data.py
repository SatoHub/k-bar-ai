"""add shap_data to prediction_logs

Revision ID: c6e0a23b4567
Revises: b5d9f12e6789
Create Date: 2026-02-20 23:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c6e0a23b4567"
down_revision: Union[str, None] = "b5d9f12e6789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prediction_logs", sa.Column("shap_data", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("prediction_logs", "shap_data")
