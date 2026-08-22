"""create horse_pedigree table (self-contained pedigree, synced from JRA-VAN)

Production (VPS) has no kbar_jravan / FDW, so the pedigree endpoint used to
return empty there. This table holds pedigree (sire/dam/paternal-grandsire/
broodmare-sire) keyed by netkeiba_id (= JV-Data kettonum), populated on the
home PC from the jravan.v_pedigree FDW view and synced to VPS as data only.
The endpoint reads from this local table instead of the FDW view.

Revision ID: e5f6a7b8c901
Revises: d4e5f6a7b890
Create Date: 2026-06-12 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c901"
down_revision: Union[str, None] = "d4e5f6a7b890"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "horse_pedigree",
        sa.Column("netkeiba_id", sa.String(length=20), primary_key=True),
        sa.Column("horse_name", sa.Text(), nullable=True),
        sa.Column("sire", sa.Text(), nullable=True),
        sa.Column("dam", sa.Text(), nullable=True),
        sa.Column("paternal_grandsire", sa.Text(), nullable=True),
        sa.Column("broodmare_sire", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="jravan_um",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("horse_pedigree")
