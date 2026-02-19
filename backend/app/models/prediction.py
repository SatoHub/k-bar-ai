import datetime
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PredictionLog(Base):
    """Step 2以降で使用する予想ログテーブル"""

    __tablename__ = "prediction_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    race_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"))
    horse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("horses.id", ondelete="CASCADE"))
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL")
    )
    predicted_position: Mapped[int | None] = mapped_column(Integer)
    predicted_score: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
