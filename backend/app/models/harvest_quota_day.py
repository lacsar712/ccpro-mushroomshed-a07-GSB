from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HarvestQuotaDay(Base):
    """出菇室 × 东八区自然日 × 等级 的采收重量配额（kg）。"""

    __tablename__ = "harvest_quota_days"
    __table_args__ = (
        UniqueConstraint("room_id", "work_date", "grade", name="uq_quota_room_date_grade"),
        CheckConstraint("cap_kg > 0", name="ck_quota_cap_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    grade: Mapped[str] = mapped_column(String(1), nullable=False)
    cap_kg: Mapped[float] = mapped_column(Float, nullable=False)

    room: Mapped["Room"] = relationship("Room", back_populates="harvest_quotas")
