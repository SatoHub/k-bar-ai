import datetime
import uuid

from sqlalchemy import Date, DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TrackConditionDetail(Base):
    """JRA公式「馬場情報」由来の含水率・クッション値（競馬場×日付単位）。

    JV-Data には無く、JRA公式サイトの開催日スクレイピングでのみ取得できる
    （過去遡及不可）。races とは (racecourse_name, race_date) で結合する。
    """

    __tablename__ = "track_condition_details"
    __table_args__ = (
        UniqueConstraint(
            "racecourse_name", "measured_date", name="uq_track_cond_course_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    racecourse_name: Mapped[str] = mapped_column(String(32), index=True)
    measured_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    cushion_value: Mapped[float | None] = mapped_column(Float)  # 芝クッション値
    turf_moisture_goal: Mapped[float | None] = mapped_column(Float)  # 芝ゴール前含水率%
    turf_moisture_4c: Mapped[float | None] = mapped_column(Float)  # 芝4コーナー含水率%
    dirt_moisture_goal: Mapped[float | None] = mapped_column(Float)  # ダートゴール前含水率%
    dirt_moisture_4c: Mapped[float | None] = mapped_column(Float)  # ダート4コーナー含水率%
    scraped_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow
    )
