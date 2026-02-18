"""Schemas for the plan emulator (compare all retail plans against actual meter data)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class EmulatorCompareRequest(BaseModel):
    nmi: str
    billing_start: date
    billing_end: date
    retailer_filter: Optional[list[str]] = None


class PeriodUsageOut(BaseModel):
    period_name: str
    kwh: float
    rate_cents_per_kwh: float
    cost_dollars: float


class PlanCostOut(BaseModel):
    retailer: str
    retailer_slug: str
    plan_name: str
    tariff_type: str
    distributor: Optional[str] = None
    state: Optional[str] = None
    supply_charge_dollars: float
    usage_charge_dollars: float
    feed_in_credit_dollars: float
    subtotal_dollars: float
    gst_dollars: float
    total_dollars: float
    period_breakdown: list[PeriodUsageOut]
    feed_in_rate_cents: Optional[float]
    feed_in_kwh: float
    delta_vs_current_dollars: Optional[float]
    delta_vs_current_percent: Optional[float]
    rank: int


class EmulatorCompareResponse(BaseModel):
    nmi: str
    billing_start: date
    billing_end: date
    billing_days: int
    total_import_kwh: float
    total_export_kwh: float
    interval_count: int
    invoiced_total: Optional[float]
    plans: list[PlanCostOut]
    cheapest_plan_name: str
    cheapest_total: float
    potential_annual_saving: Optional[float]
