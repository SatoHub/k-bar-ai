import datetime
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    __table_args__ = (Index("ix_odds_snapshots_race_post", "race_id", "post_position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    race_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("races.id", ondelete="CASCADE"), index=True
    )
    post_position: Mapped[int] = mapped_column(SmallInteger)
    win_odds: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    win_favorite: Mapped[int | None] = mapped_column(SmallInteger)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
