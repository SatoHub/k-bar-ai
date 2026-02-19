import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    entries: Mapped[list["RaceEntry"]] = relationship(back_populates="trainer")  # noqa: F821
