"""ORM models for persisted invoices and reconciliation results."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    nmi: Mapped[str | None] = mapped_column(String(16), nullable=True)
    retailer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    energy_plan_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    network_provider: Mapped[str | None] = mapped_column(String(128), nullable=True)

    invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(16), nullable=True)

    billing_period_start: Mapped[str | None] = mapped_column(String(16), nullable=True)
    billing_period_end: Mapped[str | None] = mapped_column(String(16), nullable=True)

    service_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    service_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    service_postcode: Mapped[str | None] = mapped_column(String(8), nullable=True)

    subtotal: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    gst: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    total: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_due: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLineItem.sort_order"
    )


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    charge_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(16, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rate: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    tariff_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    invoice: Mapped[Invoice] = relationship(back_populates="line_items")


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reconciliation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )

    nem12_file_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    network_tariff_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retail_plan_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    overall_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    invoiced_total: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    calculated_total: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_difference: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    recommendations_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
