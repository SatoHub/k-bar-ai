import datetime
import uuid

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    direction: Mapped[str] = mapped_column(String(8))  # outgoing / incoming
    message_type: Mapped[str] = mapped_column(String(16))  # text / flex
    category: Mapped[str] = mapped_column(
        String(32)
    )  # prediction / results / weekly / test / webhook
    status: Mapped[str] = mapped_column(String(16))  # success / error / skipped
    payload: Mapped[dict | None] = mapped_column(JSONB)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
