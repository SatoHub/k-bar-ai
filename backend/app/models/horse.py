import uuid

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Horse(Base):
    __tablename__ = "horses"
    __table_args__ = (UniqueConstraint("name", "sex", name="uq_horses_name_sex"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), index=True)
    sex: Mapped[str | None] = mapped_column(String(8))
    netkeiba_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    image_url: Mapped[str | None] = mapped_column(String(256))

    entries: Mapped[list["RaceEntry"]] = relationship(back_populates="horse")  # noqa: F821
