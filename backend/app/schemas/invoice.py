"""Invoice schemas."""
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ChargeType(str, Enum):
    """Types of charges on energy invoices."""

    USAGE = "usage"  # Energy consumption charges
    DEMAND = "demand"  # Demand charges (kW)
    SUPPLY = "supply"  # Daily supply charge
    NETWORK = "network"  # Network (distribution) charges
    METERING = "metering"  # Metering service charges
    ENVIRONMENTAL = "environmental"  # Green schemes, RECs, etc.
    GST = "gst"  # Goods and Services Tax
    OTHER = "other"


class InvoiceLineItem(BaseModel):
    """Single line item from an invoice."""

    description: str
    charge_type: ChargeType
    quantity: Optional[float] = None  # kWh, kW, or days
    unit: Optional[str] = None  # kWh, kW, day
    rate: Optional[Decimal] = None  # $/unit
    amount: Decimal  # Total charge (excl GST unless charge_type is GST)
    tariff_code: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class ParsedInvoice(BaseModel):
    """Invoice parsed from PDF."""

    invoice_number: str
    invoice_date: date
    due_date: Optional[date] = None
    retailer: str
    nmi: str
    billing_period_start: date
    billing_period_end: date
    line_items: list[InvoiceLineItem]
    subtotal: Decimal
    gst: Decimal
    total: Decimal
    previous_balance: Optional[Decimal] = None
    payments_received: Optional[Decimal] = None
    amount_due: Decimal


class CalculatedInvoice(BaseModel):
    """Invoice calculated from consumption data and tariffs."""

    nmi: str
    billing_period_start: date
    billing_period_end: date
    line_items: list[InvoiceLineItem]
    subtotal: Decimal
    gst: Decimal
    total: Decimal
    calculation_notes: Optional[str] = None


class InvoiceUploadResponse(BaseModel):
    """Response after uploading invoice PDF."""

    file_id: str
    filename: str
    parsed_invoice: ParsedInvoice
    confidence_score: float = Field(..., ge=0, le=1)
    warnings: list[str] = []
