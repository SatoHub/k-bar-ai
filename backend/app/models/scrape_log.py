import datetime
import uuid

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(String(16))  # shutuba/odds/result
    target_date: Mapped[datetime.date | None] = mapped_column(Date)
    target_race_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))  # success/error/partial
    records_affected: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
