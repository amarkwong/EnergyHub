"""ORM model for persisted interval meter data."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MeterDataInterval(Base):
    """Persisted interval rows from NEM12-like and retailer CSV sources."""

    __tablename__ = "meter_data_intervals"
    __table_args__ = (
        UniqueConstraint("file_id", "nmi", "register_code", "start_at", name="uq_meter_interval_row"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_format: Mapped[str] = mapped_column(String(32), nullable=False, default="retailer_csv", index=True)

    account_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    nmi: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    device_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    register_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    rate_type_description: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval_length_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    profile_read_value: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    register_read_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 6), nullable=True)
    quality_flag: Mapped[str | None] = mapped_column(String(8), nullable=True)

