"""create notification_logs table

Revision ID: a1b2c3d4e567
Revises: f9a3b56c7890
Create Date: 2026-02-21 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e567"
down_revision: Union[str, None] = "f9a3b56c7890"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("message_type", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_logs")),
    )
    op.create_index(
        op.f("ix_notification_logs_category"),
        "notification_logs",
        ["category"],
    )
    op.create_index(
        op.f("ix_notification_logs_created_at"),
        "notification_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notification_logs_created_at"), table_name="notification_logs"
    )
    op.drop_index(op.f("ix_notification_logs_category"), table_name="notification_logs")
    op.drop_table("notification_logs")
