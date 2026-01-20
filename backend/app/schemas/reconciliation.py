"""Invoice reconciliation schemas."""
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.invoice import ChargeType


class DiscrepancyStatus(str, Enum):
    """Status of a line item discrepancy."""

    MATCH = "match"  # Values match within tolerance
    MINOR = "minor"  # Small discrepancy (< 5%)
    SIGNIFICANT = "significant"  # Significant discrepancy (>= 5%)
    MISSING_INVOICED = "missing_invoiced"  # Item on invoice but not calculated
    MISSING_CALCULATED = "missing_calculated"  # Item calculated but not on invoice


class LineItemReconciliation(BaseModel):
    """Reconciliation result for a single line item."""

    description: str
    charge_type: ChargeType

    # Invoiced values
    invoiced_quantity: Optional[float] = None
    invoiced_rate: Optional[Decimal] = None
    invoiced_amount: Decimal

    # Calculated values
    calculated_quantity: Optional[float] = None
    calculated_rate: Optional[Decimal] = None
    calculated_amount: Optional[Decimal] = None

    # Discrepancy
    amount_difference: Decimal
    percentage_difference: Optional[float] = None
    status: DiscrepancyStatus

    # Notes
    notes: Optional[str] = None


class ReconciliationSummary(BaseModel):
    """Summary of invoice reconciliation."""

    nmi: str
    invoice_number: str
    billing_period_start: date
    billing_period_end: date

    # Totals
    invoiced_total: Decimal
    calculated_total: Decimal
    total_difference: Decimal
    total_percentage_difference: float

    # Line item breakdown
    line_items: list[LineItemReconciliation]

    # Summary counts
    matched_items: int
    minor_discrepancies: int
    significant_discrepancies: int
    missing_items: int

    # Overall status
    overall_status: DiscrepancyStatus
    confidence_score: float = Field(..., ge=0, le=1)

    # Recommendations
    recommendations: list[str] = []


class ReconciliationRequest(BaseModel):
    """Request to reconcile an invoice."""

    invoice_file_id: str
    nem12_file_id: str
    network_tariff_code: Optional[str] = None
    retail_plan_name: Optional[str] = None
    tolerance_percent: float = Field(default=1.0, ge=0, le=100)


class ReconciliationHistoryItem(BaseModel):
    """Historical reconciliation record."""

    reconciliation_id: str
    nmi: str
    invoice_number: str
    billing_period_start: date
    billing_period_end: date
    overall_status: DiscrepancyStatus
    total_difference: Decimal
    reconciled_at: date
