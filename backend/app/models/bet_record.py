import datetime
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BetRecord(Base):
    __tablename__ = "bet_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    race_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("races.id", ondelete="SET NULL"), nullable=True
    )
    bet_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    bet_type: Mapped[str] = mapped_column(String(16), nullable=False)
    horse_names: Mapped[str] = mapped_column(Text, nullable=False)
    amount_yen: Mapped[int] = mapped_column(Integer, nullable=False)
    odds_at_bet: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    actual_payout: Mapped[int | None] = mapped_column(Integer)
    is_hit: Mapped[bool | None] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
