import datetime
import uuid

from sqlalchemy import Date, Index, SmallInteger, String, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Race(Base):
    __tablename__ = "races"
    __table_args__ = (Index("ix_races_date_course", "race_date", "racecourse_code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    race_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    race_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    racecourse_code: Mapped[str | None] = mapped_column(String(8))
    racecourse_name: Mapped[str | None] = mapped_column(String(32))
    race_number: Mapped[int | None] = mapped_column(SmallInteger)
    race_name: Mapped[str | None] = mapped_column(String(128))
    surface: Mapped[str | None] = mapped_column(String(16))
    distance_m: Mapped[int | None] = mapped_column(SmallInteger)
    weather: Mapped[str | None] = mapped_column(String(16))
    track_condition: Mapped[str | None] = mapped_column(String(16))
    direction: Mapped[str | None] = mapped_column(String(10))
    graded_race: Mapped[str | None] = mapped_column(String(50))
    race_symbols: Mapped[dict | None] = mapped_column(JSONB)
    post_time: Mapped[datetime.time | None] = mapped_column(Time)
    data_source: Mapped[str | None] = mapped_column(String(16))

    entries: Mapped[list["RaceEntry"]] = relationship(back_populates="race")  # noqa: F821
