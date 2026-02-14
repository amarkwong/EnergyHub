"""ORM models for authentication, NMI ownership, and plan assignments."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # residential|business
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    nmis: Mapped[list["UserNmi"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped[User] = relationship(back_populates="sessions")


class UserNmi(Base):
    __tablename__ = "user_nmis"
    __table_args__ = (UniqueConstraint("user_id", "nmi", name="uq_user_nmi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    nmi: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    service_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    suburb: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    postcode: Mapped[str | None] = mapped_column(String(8), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocode_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped[User] = relationship(back_populates="nmis")
    assignments: Mapped[list["UserNmiPlanAssignment"]] = relationship(back_populates="user_nmi", cascade="all, delete-orphan")


class UserNmiPlanAssignment(Base):
    __tablename__ = "user_nmi_plan_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_nmi_id: Mapped[int] = mapped_column(ForeignKey("user_nmis.id", ondelete="CASCADE"), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    retailer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retail_plan_id: Mapped[int | None] = mapped_column(ForeignKey("energy_plans.id", ondelete="SET NULL"), nullable=True)
    network_tariff_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_invoice_file_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user_nmi: Mapped[UserNmi] = relationship(back_populates="assignments")
