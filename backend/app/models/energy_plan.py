"""ORM models for retailers, plans, and TOU definitions."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Retailer(Base):
    __tablename__ = "retailers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    plans: Mapped[list["EnergyPlan"]] = relationship(back_populates="retailer", cascade="all, delete-orphan")


class EnergyPlan(Base):
    __tablename__ = "energy_plans"
    __table_args__ = (
        UniqueConstraint("retailer_id", "plan_name", "effective_from", "network_provider", name="uq_energy_plan_ver"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    retailer_id: Mapped[int] = mapped_column(ForeignKey("retailers.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    network_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tariff_type: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_supply_charge_cents: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    usage_rate_cents_per_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    feed_in_tariff_cents_per_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    feed_in_tariffs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    retailer: Mapped[Retailer] = relationship(back_populates="plans")
    tou_definitions: Mapped[list["TouDefinition"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class TouDefinition(Base):
    __tablename__ = "tou_definitions"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_key", "name", "effective_from", "plan_id", name="uq_tou_definition_ver"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # retailer|network
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # retailer slug or provider code
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Australia/Sydney", nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("energy_plans.id", ondelete="SET NULL"), nullable=True, index=True)

    plan: Mapped[EnergyPlan | None] = relationship(back_populates="tou_definitions")
    periods: Mapped[list["TouPeriod"]] = relationship(back_populates="definition", cascade="all, delete-orphan")


class TouPeriod(Base):
    __tablename__ = "tou_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    definition_id: Mapped[int] = mapped_column(
        ForeignKey("tou_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    days_of_week: Mapped[str] = mapped_column(String(64), nullable=False)  # CSV format: "0,1,2,3,4"
    rate_cents_per_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    demand_rate_cents_per_kva: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="kWh", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    definition: Mapped[TouDefinition] = relationship(back_populates="periods")
