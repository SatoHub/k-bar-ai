import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RaceEntry(Base):
    __tablename__ = "race_entries"
    __table_args__ = (
        Index("ix_race_entries_race_post", "race_id", "post_position", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    race_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("races.id", ondelete="CASCADE"), index=True
    )
    horse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("horses.id", ondelete="CASCADE"), index=True
    )
    jockey_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jockeys.id", ondelete="SET NULL")
    )
    trainer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trainers.id", ondelete="SET NULL")
    )

    bracket_number: Mapped[int | None] = mapped_column(SmallInteger)
    post_position: Mapped[int | None] = mapped_column(SmallInteger)
    horse_age: Mapped[int | None] = mapped_column(SmallInteger)
    weight_carried_kg: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    finish_position: Mapped[int | None] = mapped_column(SmallInteger, index=True)
    finish_note: Mapped[str | None] = mapped_column(String(10))
    total_time_tenths: Mapped[int | None] = mapped_column(Integer)
    margin: Mapped[str | None] = mapped_column(String(20))

    corner_pos_1: Mapped[str | None] = mapped_column(String(20))
    corner_pos_2: Mapped[str | None] = mapped_column(String(20))
    corner_pos_3: Mapped[str | None] = mapped_column(String(20))
    corner_pos_4: Mapped[str | None] = mapped_column(String(20))
    last_3f_time: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    win_odds: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    win_favorite: Mapped[int | None] = mapped_column(SmallInteger)

    horse_weight_kg: Mapped[int | None] = mapped_column(SmallInteger)
    horse_weight_diff: Mapped[int | None] = mapped_column(SmallInteger)

    owner: Mapped[str | None] = mapped_column(String(100))
    prize_money_10k_yen: Mapped[Decimal | None] = mapped_column(Numeric(10, 1))
    data_source: Mapped[str | None] = mapped_column(String(16))

    # Relationships
    race: Mapped["Race"] = relationship(back_populates="entries")  # noqa: F821
    horse: Mapped["Horse"] = relationship(back_populates="entries")  # noqa: F821
    jockey: Mapped["Jockey | None"] = relationship(back_populates="entries")  # noqa: F821
    trainer: Mapped["Trainer | None"] = relationship(back_populates="entries")  # noqa: F821
